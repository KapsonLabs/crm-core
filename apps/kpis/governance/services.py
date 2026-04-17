from apps.kpis.application.contracts import TenantContext
from apps.kpis.application.services.kpi_definition_service import KpiDefinitionService


class VersionGovernanceService:
    """Governance facade for approval/publish controls."""

    def __init__(self, definition_service: KpiDefinitionService):
        self.definition_service = definition_service

    def approve(self, tenant: TenantContext, *, kpi_id: str, version: int) -> dict:
        return self.definition_service.approve_version(tenant, kpi_id=kpi_id, version=version)

    def publish(self, tenant: TenantContext, *, kpi_id: str, version: int) -> dict:
        return self.definition_service.publish_version(tenant, kpi_id=kpi_id, version=version)
