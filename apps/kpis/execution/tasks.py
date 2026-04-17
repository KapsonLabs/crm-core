from __future__ import annotations

from celery import shared_task

from apps.kpis.application.contracts import TenantContext
from apps.kpis.application.factory import build_kpi_execution_service


def _parse_version_id(kpi_version_id: str) -> tuple[str, int]:
    # Composite ID format for phase-1 transitional version storage: <kpi_id>:<version>
    kpi_id, version_raw = kpi_version_id.rsplit(":", 1)
    return kpi_id, int(version_raw)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def run_kpi_version(
    self,
    organization_id: str,
    kpi_version_id: str,
    window: dict,
    trigger: str,
):
    execution_service = build_kpi_execution_service()
    kpi_id, version = _parse_version_id(kpi_version_id)
    tenant = TenantContext(organization_id=organization_id, request_id=self.request.id)
    return execution_service.run(
        tenant,
        kpi_id=kpi_id,
        version=version,
        window=window,
        trigger=trigger,
    )
