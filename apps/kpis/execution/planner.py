import hashlib
from datetime import date
from typing import Any

from apps.kpis.domain.exceptions import ExecutionPlanningError


class DefaultExecutionPlanner:
    """Normalizes runtime period specs and builds execution metadata."""

    def build_plan(
        self,
        tenant_ctx,
        kpi_id: str,
        kpi_version: dict[str, Any],
        period_spec: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            window_kind = period_spec["kind"]
            window_start = date.fromisoformat(period_spec["start"])
            window_end = date.fromisoformat(period_spec["end"])
        except (KeyError, ValueError) as exc:
            raise ExecutionPlanningError("Invalid execution window spec.") from exc

        if window_start > window_end:
            raise ExecutionPlanningError("Window start cannot be after window end.")

        base_key = (
            f"{tenant_ctx.organization_id}:{kpi_id}:{kpi_version['version']}:"
            f"{window_start.isoformat()}:{window_end.isoformat()}:all"
        )
        idempotency_key = hashlib.sha256(base_key.encode("utf-8")).hexdigest()

        return {
            "window": {
                "kind": window_kind,
                "start": window_start,
                "end": window_end,
            },
            "idempotency_key": idempotency_key,
        }
