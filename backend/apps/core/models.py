from collections.abc import Mapping
from typing import ClassVar

from django.db import models

from .exceptions import InvalidStateTransition
from .money import DECIMAL_PLACES, MAX_DIGITS


def money_field(**kwargs) -> models.DecimalField:
    """NUMERIC(14,2): up to 999,999,999,999.99 rupees."""
    return models.DecimalField(max_digits=MAX_DIGITS, decimal_places=DECIMAL_PLACES, **kwargs)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StateMachineMixin:
    """Declarative status transitions; services call `transition_to` instead of assigning status."""

    TRANSITIONS: ClassVar[Mapping[str, frozenset[str]]] = {}

    def allowed_transitions(self) -> frozenset[str]:
        return self.TRANSITIONS.get(self.status, frozenset())

    def can_transition_to(self, target: str) -> bool:
        return target in self.allowed_transitions()

    def transition_to(self, target: str) -> None:
        if not self.can_transition_to(target):
            raise InvalidStateTransition(
                f"Cannot move {self._meta.verbose_name} from {self.status} to {target}.",
                details={
                    "entity": self._meta.model_name,
                    "id": self.pk,
                    "from": self.status,
                    "to": target,
                },
            )
        self.status = target


class DocumentSequence(TimeStampedModel):
    """Gap-free counter behind human-readable document numbers (receipts, deposits, ...)."""

    prefix = models.CharField(max_length=10)
    scope = models.CharField(max_length=20, blank=True)
    period = models.DateField(null=True, blank=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["prefix", "scope", "period"],
                nulls_distinct=False,
                name="uniq_document_sequence",
            ),
        ]

    def __str__(self):
        return f"{self.prefix}/{self.scope or '-'}/{self.period or '-'} = {self.last_value}"
