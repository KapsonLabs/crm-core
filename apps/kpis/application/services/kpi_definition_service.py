from datetime import date

from apps.kpis.application.contracts import AuditWriter, KpiVersionRepository, TenantContext


class KpiDefinitionService:
    """Application service for KPI draft/approval/publication lifecycle."""

    def __init__(self, version_repo: KpiVersionRepository, audit_writer: AuditWriter):
        self.version_repo = version_repo
        self.audit_writer = audit_writer

    def create_draft_version(self, tenant: TenantContext, *, kpi_id: str, formula: str) -> dict:
        payload = {
            "kpi_id": kpi_id,
            "formula": formula,
            "created_by": tenant.user_id,
        }
        draft = self.version_repo.save_draft(tenant, payload)
        self.audit_writer.write(
            tenant,
            event_type="kpi_version.draft_created",
            payload={"kpi_id": kpi_id, "version": draft["version"]},
        )
        return draft

    def approve_version(self, tenant: TenantContext, *, kpi_id: str, version: int) -> dict:
        approved = self.version_repo.transition_status(
            tenant=tenant,
            kpi_id=kpi_id,
            version=version,
            target_status="approved",
            actor_id=tenant.user_id,
        )
        self.audit_writer.write(
            tenant,
            event_type="kpi_version.approved",
            payload={"kpi_id": kpi_id, "version": version},
        )
        return approved

    def publish_version(self, tenant: TenantContext, *, kpi_id: str, version: int) -> dict:
        published = self.version_repo.transition_status(
            tenant=tenant,
            kpi_id=kpi_id,
            version=version,
            target_status="published",
            actor_id=tenant.user_id,
        )
        self.audit_writer.write(
            tenant,
            event_type="kpi_version.published",
            payload={"kpi_id": kpi_id, "version": version},
        )
        return published

    def get_published_for_date(self, tenant: TenantContext, *, kpi_id: str, as_of: date) -> dict:
        return self.version_repo.get_published(tenant, kpi_id, as_of)
