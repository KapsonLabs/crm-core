import json
import logging
from typing import Any

from apps.kpis.application.contracts import AuditWriter, TenantContext

logger = logging.getLogger("kpi.audit")


class StructuredAuditWriter(AuditWriter):
    """Structured audit logger used until persistent audit models are added."""

    def write(self, tenant: TenantContext, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "event_type": event_type,
            "organization_id": tenant.organization_id,
            "actor_id": tenant.user_id,
            "request_id": tenant.request_id,
            "payload": payload,
        }
        logger.info(json.dumps(event, default=str, sort_keys=True))
