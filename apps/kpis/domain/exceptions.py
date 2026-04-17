class KpiDomainError(Exception):
    """Base exception for KPI domain errors."""


class TenantIsolationError(KpiDomainError):
    """Raised when an operation attempts cross-tenant access."""


class InvalidLifecycleTransition(KpiDomainError):
    """Raised when version status transition is invalid."""


class VersionNotFound(KpiDomainError):
    """Raised when KPI version cannot be resolved."""


class FormulaCompilationError(KpiDomainError):
    """Raised when formula cannot be compiled into SQL."""


class ExecutionPlanningError(KpiDomainError):
    """Raised when execution plan generation fails."""
