from apps.accounts.models import User
from apps.accounts.permissions import HasRole

# Team-level views (branch and agent tables, deposit exports); agents get their own stats only.
IsSupervisor = HasRole(User.Role.ADMIN, User.Role.FINANCE, User.Role.BRANCH_MANAGER)
