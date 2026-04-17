from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class TenantContext:
    organization_id: str
    user_id: str | None = None
    request_id: str | None = None


class KpiVersionRepository(Protocol):
    def get_published(self, tenant: TenantContext, kpi_id: str, as_of: date) -> dict[str, Any]: ...

    def get_version(self, tenant: TenantContext, kpi_id: str, version: int) -> dict[str, Any]: ...

    def save_draft(self, tenant: TenantContext, payload: dict[str, Any]) -> dict[str, Any]: ...

    def transition_status(
        self,
        tenant: TenantContext,
        kpi_id: str,
        version: int,
        target_status: str,
        actor_id: str | None,
    ) -> dict[str, Any]: ...


class FormulaCompiler(Protocol):
    def compile_to_sql_template(self, tenant: TenantContext, formula: str) -> dict[str, Any]: ...


class SnapshotRepository(Protocol):
    def create_immutable_snapshot(
        self,
        tenant: TenantContext,
        snapshot_payload: dict[str, Any],
    ) -> dict[str, Any]: ...


class AuditWriter(Protocol):
    def write(self, tenant: TenantContext, event_type: str, payload: dict[str, Any]) -> None: ...


class SqlExecutor(Protocol):
    def execute(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...
