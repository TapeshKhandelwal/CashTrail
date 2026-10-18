"""Role checks. Compose with DRF operators, e.g. `IsAdmin | (IsFinance & ReadOnly)`.

Row-level access is enforced by queryset scoping (see `apps.accounts.scoping`),
so out-of-scope records surface as 404 rather than 403.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User


def HasRole(*roles: str) -> type[BasePermission]:
    allowed = frozenset(roles)

    class _HasRole(BasePermission):
        message = "Your role is not allowed to perform this action."

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.role in allowed)

    _HasRole.__name__ = _HasRole.__qualname__ = f"HasRole({', '.join(sorted(allowed))})"
    return _HasRole


IsAdmin = HasRole(User.Role.ADMIN)
IsBranchManager = HasRole(User.Role.BRANCH_MANAGER)
IsAgent = HasRole(User.Role.AGENT)
IsFinance = HasRole(User.Role.FINANCE)
IsAdminOrBranchManager = HasRole(User.Role.ADMIN, User.Role.BRANCH_MANAGER)
IsAdminOrFinance = HasRole(User.Role.ADMIN, User.Role.FINANCE)


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
