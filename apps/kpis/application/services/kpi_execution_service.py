from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.kpis.application.contracts import (
    AuditWriter,
    FormulaCompiler,
    KpiVersionRepository,
    SnapshotRepository,
    SqlExecutor,
    TenantContext,
)
from apps.kpis.domain.entities import LifecycleState
from apps.kpis.domain.exceptions import InvalidLifecycleTransition
from apps.kpis.execution.contracts import ExecutionPlanner


class KpiExecutionService:
    """Application service for compile -> execute -> snapshot workflow."""

    def __init__(
        self,
        *,
        version_repo: KpiVersionRepository,
        planner: ExecutionPlanner,
        compiler: FormulaCompiler,
        sql_executor: SqlExecutor,
        snapshot_repo: SnapshotRepository,
        audit_writer: AuditWriter,
    ):
        self.version_repo = version_repo
        self.planner = planner
        self.compiler = compiler
        self.sql_executor = sql_executor
        self.snapshot_repo = snapshot_repo
        self.audit_writer = audit_writer

    def run(
        self,
        tenant: TenantContext,
        *,
        kpi_id: str,
        window: dict[str, Any],
        trigger: str,
        version: int | None = None,
    ) -> dict[str, Any]:
        as_of = date.fromisoformat(window["end"])
        version_data = self._resolve_version(tenant, kpi_id, as_of, version)

        plan = self.planner.build_plan(
            tenant_ctx=tenant,
            kpi_id=kpi_id,
            kpi_version=version_data,
            period_spec=window,
        )
        compiled = self.compiler.compile_to_sql_template(tenant, version_data["formula"])

        rows = self.sql_executor.execute(compiled["sql"], compiled.get("params", {}))
        value = self._extract_value(rows)

        snapshot = self.snapshot_repo.create_immutable_snapshot(
            tenant,
            {
                "kpi_id": kpi_id,
                "value": value,
                "period_start": plan["window"]["start"],
                "period_end": plan["window"]["end"],
                "metadata": {
                    "execution": {
                        "trigger": trigger,
                        "idempotency_key": plan["idempotency_key"],
                        "version": version_data["version"],
                        "compiled_tables": compiled.get("metadata", {}).get("tables", []),
                    }
                },
            },
        )

        result = {
            "kpi_id": kpi_id,
            "version": version_data["version"],
            "window": {
                "kind": window["kind"],
                "start": plan["window"]["start"].isoformat(),
                "end": plan["window"]["end"].isoformat(),
            },
            "idempotency_key": plan["idempotency_key"],
            "snapshot": snapshot,
        }
        self.audit_writer.write(tenant, "kpi_execution.completed", result)
        return result

    def _resolve_version(
        self,
        tenant: TenantContext,
        kpi_id: str,
        as_of: date,
        explicit_version: int | None,
    ) -> dict[str, Any]:
        if explicit_version is None:
            return self.version_repo.get_published(tenant, kpi_id, as_of)

        version_data = self.version_repo.get_version(tenant, kpi_id, explicit_version)
        if version_data.get("status") != LifecycleState.PUBLISHED.value:
            raise InvalidLifecycleTransition(
                f"Version '{explicit_version}' is not published and cannot be executed."
            )
        return version_data

    def _extract_value(self, rows: list[dict[str, Any]]) -> Decimal:
        if not rows:
            return Decimal("0")

        row = rows[0]
        raw_value = row.get("value")
        if raw_value is None and row:
            # Fallback to first column if caller did not alias to value.
            raw_value = next(iter(row.values()))
        if raw_value is None:
            return Decimal("0")
        return Decimal(str(raw_value))
