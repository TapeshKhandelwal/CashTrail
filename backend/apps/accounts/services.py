"""User administration. Authentication itself lives in the JWT views."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.branches.models import Branch
from apps.collections.models import Collection
from apps.core.exceptions import DomainError, ValidationFailed
from apps.core.money import ZERO

from .models import User

AUDIT_FIELDS = (
    "username",
    "first_name",
    "last_name",
    "email",
    "phone",
    "role",
    "branch",
    "is_active",
)
EDITABLE_FIELDS = frozenset({"first_name", "last_name", "email", "phone", "role", "branch"})
CASH_IN_HAND = (Collection.Status.COLLECTED, Collection.Status.SUBMITTED)


def create_user(
    actor,
    *,
    username: str,
    password: str,
    role: str,
    branch: Branch | None = None,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
    phone: str = "",
) -> User:
    user = User(
        username=username,
        role=role,
        branch=_branch_for_role(role, branch),
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )
    _validate_password(password, user)
    user.set_password(password)

    with transaction.atomic():
        if User.objects.filter(username__iexact=username).exists():
            raise DomainError(
                "This username is already taken.",
                code="DUPLICATE_RECORD",
                status_code=409,
                details={"username": username},
            )
        user.save()
        log_event(actor, AuditAction.USER_CREATED, user, after=snapshot(user, AUDIT_FIELDS))
    return user


def update_user(actor, user: User, **changes) -> User:
    """Edit profile, role or branch. Global roles never carry a branch.

    A role or branch change revokes the user's refresh tokens.
    """
    unknown = changes.keys() - EDITABLE_FIELDS
    if unknown:
        raise ValidationFailed(
            "These fields cannot be changed.", details={"fields": sorted(unknown)}
        )

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        role = changes.get("role", user.role)
        if role in User.GLOBAL_ROLES or {"role", "branch"} & changes.keys():
            changes["branch"] = _branch_for_role(role, changes.get("branch", user.branch))

        changed = [field for field, value in changes.items() if getattr(user, field) != value]
        if not changed:
            return user
        if "role" in changed and user.pk == actor.pk:
            raise ValidationFailed("You cannot change your own role.")
        if user.is_agent and {"role", "branch"} & set(changed):
            _ensure_no_agent_workload(user)

        before = snapshot(user, changed)
        for field in changed:
            setattr(user, field, changes[field])
        user.save(update_fields=changed)
        # Refreshed tokens copy the old role and branch claims, so the user signs in again.
        if {"role", "branch"} & set(changed):
            _revoke_refresh_tokens(user)
        log_event(
            actor, AuditAction.USER_UPDATED, user, before=before, after=snapshot(user, changed)
        )
    return user


def deactivate_user(actor, user: User) -> User:
    """Block sign-in and revoke refresh tokens; access tokens fail on the next request."""
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if not user.is_active:
            return user
        if user.pk == actor.pk:
            raise ValidationFailed("You cannot deactivate your own account.")
        if user.is_agent:
            _ensure_no_agent_workload(user)
        _set_active(actor, user, active=False)
        _revoke_refresh_tokens(user)
    return user


def activate_user(actor, user: User) -> User:
    with transaction.atomic():
        user = User.objects.select_related("branch").select_for_update(of=("self",)).get(pk=user.pk)
        if user.is_active:
            return user
        if user.role in User.BRANCH_ROLES and not user.branch.is_active:
            raise ValidationFailed(
                "Move the user to an active branch before reactivating them.",
                details={"branch": user.branch_id},
            )
        _set_active(actor, user, active=True)
    return user


def set_password(actor, user: User, password: str) -> None:
    _validate_password(password, user)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        user.set_password(password)
        user.save(update_fields=["password"])
        _revoke_refresh_tokens(user)
        log_event(actor, AuditAction.USER_UPDATED, user, after={"password_reset": True})


def _branch_for_role(role: str, branch: Branch | None) -> Branch | None:
    if role in User.GLOBAL_ROLES:
        return None
    if branch is None:
        raise ValidationFailed(
            "Agents and branch managers must belong to a branch.",
            details={"branch": ["This field is required for this role."]},
        )
    if not branch.is_active:
        raise ValidationFailed(
            "Users cannot be assigned to an inactive branch.", details={"branch": branch.pk}
        )
    return branch


def _validate_password(password: str, user: User) -> None:
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationFailed(
            "Choose a stronger password.", details={"password": exc.messages}
        ) from exc


def _ensure_no_agent_workload(agent: User) -> None:
    """An agent who still has customers or cash in hand cannot leave their post."""
    assigned_customers = agent.assigned_customers.count()
    cash_in_hand = (
        Collection.objects.filter(
            agent=agent, mode=Collection.Mode.CASH, status__in=CASH_IN_HAND
        ).aggregate(total=Sum("amount"))["total"]
        or ZERO
    )
    if assigned_customers or cash_in_hand:
        raise ValidationFailed(
            "Reassign this agent's customers and reconcile the cash they hold first.",
            details={"assigned_customers": assigned_customers, "cash_in_hand": str(cash_in_hand)},
        )


def _set_active(actor, user: User, *, active: bool) -> None:
    user.is_active = active
    user.save(update_fields=["is_active"])
    log_event(
        actor,
        AuditAction.USER_UPDATED,
        user,
        before={"is_active": not active},
        after={"is_active": active},
    )


def _revoke_refresh_tokens(user: User) -> None:
    live_tokens = OutstandingToken.objects.filter(
        user=user, expires_at__gt=timezone.now(), blacklistedtoken__isnull=True
    )
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in live_tokens], ignore_conflicts=True
    )
