import pytest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditLog
from apps.core.exceptions import DomainError, ValidationFailed
from apps.core.testing import factories

pytestmark = pytest.mark.django_db

STRONG_PASSWORD = "Ledger-Stone-42"


def create_agent(actor, branch, **overrides):
    fields = {
        "username": "new.agent",
        "password": STRONG_PASSWORD,
        "role": User.Role.AGENT,
        "branch": branch,
        "first_name": "Ravi",
    }
    return services.create_user(actor, **(fields | overrides))


class TestCreateUser:
    def test_creates_agent_with_hashed_password_and_audit(self, admin_user, branch):
        user = create_agent(admin_user, branch)

        assert user.check_password(STRONG_PASSWORD)
        assert user.branch == branch
        log = AuditLog.objects.get(action=AuditAction.USER_CREATED)
        assert log.entity_id == str(user.pk)
        assert log.branch == branch
        assert log.after["role"] == "AGENT"
        assert "password" not in log.after

    def test_branch_roles_require_a_branch(self, admin_user):
        with pytest.raises(ValidationFailed) as exc:
            create_agent(admin_user, None)

        assert "branch" in exc.value.details

    def test_inactive_branch_is_rejected(self, admin_user):
        closed = factories.BranchFactory(code="OLD01", is_active=False)

        with pytest.raises(ValidationFailed):
            create_agent(admin_user, closed)

    def test_global_roles_never_carry_a_branch(self, admin_user, branch):
        user = create_agent(admin_user, branch, role=User.Role.FINANCE)

        assert user.branch is None

    def test_username_is_unique_ignoring_case(self, admin_user, branch, agent):
        with pytest.raises(DomainError) as exc:
            create_agent(admin_user, branch, username="AGENT")

        assert exc.value.code == "DUPLICATE_RECORD"

    def test_weak_password_is_rejected(self, admin_user, branch):
        with pytest.raises(ValidationFailed) as exc:
            create_agent(admin_user, branch, password="12345678")

        assert exc.value.details["password"]
        assert not User.objects.filter(username="new.agent").exists()


class TestUpdateUser:
    def test_promoting_agent_with_customers_is_blocked(self, admin_user, customer):
        with pytest.raises(ValidationFailed) as exc:
            services.update_user(admin_user, customer.assigned_agent, role=User.Role.BRANCH_MANAGER)

        assert exc.value.details == {"assigned_customers": 1, "cash_in_hand": "0.00"}

    def test_moving_agent_holding_cash_is_blocked(self, admin_user, agent, other_branch):
        customer = factories.CustomerFactory(branch=agent.branch, assigned_agent=agent)
        factories.CollectionFactory(loan__customer=customer, agent=agent)
        customer.assigned_agent = None
        customer.save()

        with pytest.raises(ValidationFailed) as exc:
            services.update_user(admin_user, agent, branch=other_branch)

        assert exc.value.details == {"assigned_customers": 0, "cash_in_hand": "1000.00"}

    def test_free_agent_can_move_branch(self, admin_user, agent, other_branch):
        services.update_user(admin_user, agent, branch=other_branch, phone="9000000001")

        agent.refresh_from_db()
        assert agent.branch == other_branch
        log = AuditLog.objects.get(action=AuditAction.USER_UPDATED)
        assert log.before["branch"] != log.after["branch"] == other_branch.pk
        assert log.after["phone"] == "9000000001"

    def test_switching_to_global_role_clears_branch(self, admin_user, manager):
        services.update_user(admin_user, manager, role=User.Role.FINANCE)

        manager.refresh_from_db()
        assert (manager.role, manager.branch) == (User.Role.FINANCE, None)

    def test_switching_to_branch_role_requires_branch(self, admin_user, finance_user):
        with pytest.raises(ValidationFailed):
            services.update_user(admin_user, finance_user, role=User.Role.AGENT)

    def test_admin_cannot_change_own_role(self, admin_user):
        with pytest.raises(ValidationFailed):
            services.update_user(admin_user, admin_user, role=User.Role.FINANCE)

    def test_username_is_not_editable(self, admin_user, agent):
        with pytest.raises(ValidationFailed):
            services.update_user(admin_user, agent, username="renamed")

    def test_no_change_writes_no_audit(self, admin_user, agent):
        services.update_user(admin_user, agent, first_name=agent.first_name)

        assert not AuditLog.objects.exists()

    def test_role_change_revokes_refresh_tokens(self, admin_user, manager):
        refresh = RefreshToken.for_user(manager)

        services.update_user(admin_user, manager, role=User.Role.FINANCE)

        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()

    def test_branch_change_revokes_refresh_tokens(self, admin_user, agent, other_branch):
        refresh = RefreshToken.for_user(agent)

        services.update_user(admin_user, agent, branch=other_branch)

        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()

    def test_profile_change_keeps_sessions(self, admin_user, agent):
        refresh = RefreshToken.for_user(agent)

        services.update_user(admin_user, agent, phone="9000000002")

        assert not BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()


class TestActivation:
    def test_deactivation_revokes_refresh_tokens(self, admin_user, manager):
        refresh = RefreshToken.for_user(manager)

        services.deactivate_user(admin_user, manager)

        manager.refresh_from_db()
        assert manager.is_active is False
        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()
        log = AuditLog.objects.get(action=AuditAction.USER_UPDATED)
        assert (log.before, log.after) == ({"is_active": True}, {"is_active": False})

    def test_agent_with_customers_cannot_be_deactivated(self, admin_user, customer):
        with pytest.raises(ValidationFailed):
            services.deactivate_user(admin_user, customer.assigned_agent)

    def test_cannot_deactivate_self(self, admin_user):
        with pytest.raises(ValidationFailed):
            services.deactivate_user(admin_user, admin_user)

    def test_deactivation_is_idempotent(self, admin_user, manager):
        services.deactivate_user(admin_user, manager)
        services.deactivate_user(admin_user, manager)

        assert AuditLog.objects.filter(action=AuditAction.USER_UPDATED).count() == 1

    def test_reactivation_requires_active_branch(self, admin_user, manager):
        services.deactivate_user(admin_user, manager)
        manager.branch.is_active = False
        manager.branch.save()

        with pytest.raises(ValidationFailed):
            services.activate_user(admin_user, manager)

    def test_reactivation(self, admin_user, manager):
        services.deactivate_user(admin_user, manager)

        services.activate_user(admin_user, manager)

        manager.refresh_from_db()
        assert manager.is_active is True


class TestSetPassword:
    def test_sets_password_and_revokes_sessions(self, admin_user, agent):
        refresh = RefreshToken.for_user(agent)

        services.set_password(admin_user, agent, STRONG_PASSWORD)

        agent.refresh_from_db()
        assert agent.check_password(STRONG_PASSWORD)
        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()
        log = AuditLog.objects.get(action=AuditAction.USER_UPDATED)
        assert log.after == {"password_reset": True}

    def test_password_similar_to_username_is_rejected(self, admin_user, agent):
        with pytest.raises(ValidationFailed):
            services.set_password(admin_user, agent, "agent")
