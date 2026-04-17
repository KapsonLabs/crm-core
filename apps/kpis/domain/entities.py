from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class LifecycleState(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class KpiVersion:
    kpi_id: str
    version: int
    status: LifecycleState
    formula: str
    created_at: datetime
    created_by: str | None = None
    approved_at: datetime | None = None
    approved_by: str | None = None
    published_at: datetime | None = None
    published_by: str | None = None


@dataclass(frozen=True)
class PeriodWindow:
    kind: str
    start: date
    end: date


@dataclass(frozen=True)
class CompiledFormula:
    sql: str
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotRecord:
    kpi_id: str
    value: Decimal
    period_start: date
    period_end: date
    is_calculated: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRequest:
    organization_id: str
    kpi_id: str
    version: int
    window: PeriodWindow
    trigger: str
    request_id: str | None = None
