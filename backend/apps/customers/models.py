from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Customer(TimeStampedModel):
    customer_code = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="customers"
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_customers",
        help_text="Must be an active agent of the same branch.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["branch", "assigned_agent"], name="customer_branch_agent_idx"),
            models.Index(fields=["phone"], name="customer_phone_idx"),
        ]

    def __str__(self):
        return f"{self.customer_code} · {self.full_name}"
