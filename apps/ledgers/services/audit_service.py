from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.ledgers.models import AuditLog


def emit_audit_log(
    *,
    event_type: str,
    entity_type: str,
    entity_id: str | UUID,
    branch: UUID | None,
    performed_by_id: UUID | None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        branch=branch,
        performed_by_id=performed_by_id,
        payload=payload or {},
    )
