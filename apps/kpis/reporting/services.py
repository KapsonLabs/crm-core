from datetime import date

from apps.kpis.application.contracts import TenantContext
from apps.kpis.infrastructure.repositories import DjangoSnapshotRepository


class SnapshotReportingService:
    """Read model service for snapshot-only reporting."""

    def __init__(self, snapshot_repo: DjangoSnapshotRepository):
        self.snapshot_repo = snapshot_repo

    def list_snapshots(
        self,
        tenant: TenantContext,
        *,
        kpi_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        return self.snapshot_repo.list_snapshots(
            tenant,
            kpi_id=kpi_id,
            start_date=start_date,
            end_date=end_date,
        )
