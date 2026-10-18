from django.db import models

from apps.core.models import TimeStampedModel


class Branch(TimeStampedModel):
    code = models.CharField(
        max_length=10, unique=True, help_text="Short uppercase code, e.g. BLR01."
    )
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "branches"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__regex=r"^[A-Z0-9]{2,10}$"),
                name="branch_code_format",
            ),
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"
