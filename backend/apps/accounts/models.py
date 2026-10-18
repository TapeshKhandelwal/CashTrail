from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        BRANCH_MANAGER = "BRANCH_MANAGER", "Branch Manager"
        AGENT = "AGENT", "Collection Agent"
        FINANCE = "FINANCE", "Finance / HQ"

    BRANCH_ROLES = frozenset({Role.BRANCH_MANAGER, Role.AGENT})
    GLOBAL_ROLES = frozenset({Role.ADMIN, Role.FINANCE})

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    phone = models.CharField(max_length=15, blank=True)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        db_index=False,
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(role__in=["AGENT", "BRANCH_MANAGER"])
                | models.Q(branch__isnull=False),
                name="user_branch_required_for_branch_roles",
            ),
        ]
        indexes = [models.Index(fields=["branch", "role"], name="user_branch_role_idx")]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_branch_manager(self) -> bool:
        return self.role == self.Role.BRANCH_MANAGER

    @property
    def is_agent(self) -> bool:
        return self.role == self.Role.AGENT

    @property
    def is_finance(self) -> bool:
        return self.role == self.Role.FINANCE

    @property
    def has_global_scope(self) -> bool:
        return self.role in self.GLOBAL_ROLES
