from collections.abc import Iterable, Mapping
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from django.db import models

from apps.core.context import get_request_context

from .models import AuditAction, AuditLog


def to_jsonable(value: Any) -> Any:
    """JSON-safe copy: money stays exact as a string, dates become ISO-8601, models become ids."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        raise TypeError("Floats are not allowed in the audit trail.")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Iterable):
        return [to_jsonable(item) for item in value]
    return str(value)


def snapshot(instance: models.Model, fields: Iterable[str]) -> dict[str, Any]:
    """Field values of `instance` (foreign keys as ids) for before/after diffs."""
    result = {}
    for name in fields:
        field = instance._meta.get_field(name)
        result[name] = getattr(instance, field.attname)
    return to_jsonable(result)


def log_event(
    actor,
    action: AuditAction | str,
    entity: models.Model,
    *,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Record a change; call inside the service transaction so the entry commits with it."""
    context = get_request_context()
    return AuditLog.objects.create(
        actor=actor if actor is not None and actor.is_authenticated else None,
        action=str(action),
        entity_type=entity._meta.model_name,
        entity_id=str(entity.pk),
        branch_id=_branch_id(entity),
        before=to_jsonable(before) if before is not None else None,
        after=to_jsonable(after) if after is not None else None,
        ip_address=context.ip_address,
        user_agent=context.user_agent,
        request_id=context.request_id,
    )


def _branch_id(entity: models.Model) -> int | None:
    if entity._meta.model_name == "branch":
        return entity.pk
    return getattr(entity, "branch_id", None)
