from typing import Any, Protocol


class ExecutionPlanner(Protocol):
    def build_plan(self, tenant_ctx, kpi_id: str, kpi_version: dict[str, Any], period_spec: dict[str, Any]) -> dict[str, Any]: ...


class SqlExecutor(Protocol):
    def execute(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]: ...
