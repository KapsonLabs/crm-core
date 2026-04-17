from apps.kpis.application.services.kpi_definition_service import KpiDefinitionService
from apps.kpis.application.services.kpi_execution_service import KpiExecutionService
from apps.kpis.execution.planner import DefaultExecutionPlanner
from apps.kpis.infrastructure.audit import StructuredAuditWriter
from apps.kpis.infrastructure.compiler import SimpleDslSqlCompiler
from apps.kpis.infrastructure.repositories import DjangoKpiVersionRepository, DjangoSnapshotRepository
from apps.kpis.infrastructure.sql_executor import DjangoSqlExecutor
from apps.kpis.reporting.services import SnapshotReportingService


def build_kpi_definition_service() -> KpiDefinitionService:
    return KpiDefinitionService(
        version_repo=DjangoKpiVersionRepository(),
        audit_writer=StructuredAuditWriter(),
    )


def build_kpi_execution_service() -> KpiExecutionService:
    return KpiExecutionService(
        version_repo=DjangoKpiVersionRepository(),
        planner=DefaultExecutionPlanner(),
        compiler=SimpleDslSqlCompiler(),
        sql_executor=DjangoSqlExecutor(),
        snapshot_repo=DjangoSnapshotRepository(),
        audit_writer=StructuredAuditWriter(),
    )


def build_snapshot_reporting_service() -> SnapshotReportingService:
    return SnapshotReportingService(snapshot_repo=DjangoSnapshotRepository())
