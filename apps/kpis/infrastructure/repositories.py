from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.kpis.application.contracts import KpiVersionRepository, SnapshotRepository, TenantContext
from apps.kpis.domain.entities import LifecycleState
from apps.kpis.domain.exceptions import TenantIsolationError, VersionNotFound
from apps.kpis.domain.policies import ensure_lifecycle_transition
from apps.kpis.models import KPI, KPIEntry


class DjangoKpiVersionRepository(KpiVersionRepository):
    """
    Transitional version storage backed by KPI.scoring_config.

    Phase 2 will migrate this to dedicated version tables.
    """

    _ENGINE_KEY = "engine"
    _VERSIONS_KEY = "versions"

    def save_draft(self, tenant: TenantContext, payload: dict[str, Any]) -> dict[str, Any]:
        kpi = self._get_tenant_kpi(tenant, payload["kpi_id"])
        config = deepcopy(kpi.scoring_config or {})
        versions = self._versions(config)
        next_version = max((int(item.get("version", 0)) for item in versions), default=0) + 1

        version = {
            "version": next_version,
            "status": LifecycleState.DRAFT.value,
            "formula": payload["formula"],
            "created_at": timezone.now().isoformat(),
            "created_by": payload.get("created_by"),
            "approved_at": None,
            "approved_by": None,
            "published_at": None,
            "published_by": None,
        }
        versions.append(version)
        kpi.scoring_config = config
        # Keep compatibility with legacy consumers that read KPI.formula directly.
        kpi.formula = payload["formula"]
        kpi.save(update_fields=["scoring_config", "formula", "updated_at"])
        return version

    def get_published(self, tenant: TenantContext, kpi_id: str, as_of: date) -> dict[str, Any]:
        kpi = self._get_tenant_kpi(tenant, kpi_id)
        versions = self._versions(kpi.scoring_config or {})

        eligible: list[dict[str, Any]] = []
        for item in versions:
            if item.get("status") != LifecycleState.PUBLISHED.value:
                continue
            published_at = self._safe_parse_datetime(item.get("published_at"))
            if published_at and published_at.date() <= as_of:
                eligible.append(item)

        if not eligible:
            raise VersionNotFound(f"No published KPI version found for KPI '{kpi_id}'.")

        return max(eligible, key=lambda version: int(version["version"]))

    def get_version(self, tenant: TenantContext, kpi_id: str, version: int) -> dict[str, Any]:
        kpi = self._get_tenant_kpi(tenant, kpi_id)
        versions = self._versions(kpi.scoring_config or {})
        for item in versions:
            if int(item.get("version", -1)) == int(version):
                return item
        raise VersionNotFound(f"Version '{version}' for KPI '{kpi_id}' was not found.")

    def transition_status(
        self,
        tenant: TenantContext,
        kpi_id: str,
        version: int,
        target_status: str,
        actor_id: str | None,
    ) -> dict[str, Any]:
        with transaction.atomic():
            kpi = self._get_tenant_kpi(tenant, kpi_id)
            config = deepcopy(kpi.scoring_config or {})
            versions = self._versions(config)

            target_item = None
            for item in versions:
                if int(item.get("version", -1)) == int(version):
                    target_item = item
                    break

            if target_item is None:
                raise VersionNotFound(f"Version '{version}' for KPI '{kpi_id}' was not found.")

            current_state = LifecycleState(target_item["status"])
            next_state = LifecycleState(target_status)
            ensure_lifecycle_transition(current_state, next_state)

            if next_state == LifecycleState.PUBLISHED:
                now_iso = timezone.now().isoformat()
                # Keep one active published version per KPI.
                for item in versions:
                    if (
                        item is not target_item
                        and item.get("status") == LifecycleState.PUBLISHED.value
                    ):
                        item["status"] = LifecycleState.ARCHIVED.value
                target_item["status"] = LifecycleState.PUBLISHED.value
                target_item["published_at"] = now_iso
                target_item["published_by"] = actor_id
                kpi.formula = target_item.get("formula") or ""
            elif next_state == LifecycleState.APPROVED:
                target_item["status"] = LifecycleState.APPROVED.value
                target_item["approved_at"] = timezone.now().isoformat()
                target_item["approved_by"] = actor_id
            elif next_state == LifecycleState.ARCHIVED:
                target_item["status"] = LifecycleState.ARCHIVED.value

            kpi.scoring_config = config
            kpi.save(update_fields=["scoring_config", "formula", "updated_at"])

        return target_item

    def _get_tenant_kpi(self, tenant: TenantContext, kpi_id: str) -> KPI:
        kpi = KPI.objects.filter(id=kpi_id).select_related("organization").first()
        if not kpi or str(kpi.organization_id) != str(tenant.organization_id):
            raise TenantIsolationError("KPI is outside the tenant scope.")
        return kpi

    def _versions(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        engine = config.setdefault(self._ENGINE_KEY, {})
        versions = engine.setdefault(self._VERSIONS_KEY, [])
        return versions

    def _safe_parse_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None


class DjangoSnapshotRepository(SnapshotRepository):
    """Snapshot repository using KPIEntry as the transitional snapshot store."""

    def create_immutable_snapshot(
        self,
        tenant: TenantContext,
        snapshot_payload: dict[str, Any],
    ) -> dict[str, Any]:
        kpi = self._get_tenant_kpi(tenant, snapshot_payload["kpi_id"])

        period_start = self._to_date(snapshot_payload["period_start"])
        period_end = self._to_date(snapshot_payload["period_end"])
        value = Decimal(str(snapshot_payload["value"]))
        metadata = snapshot_payload.get("metadata", {}) or {}

        entry, created = KPIEntry.objects.get_or_create(
            kpi=kpi,
            period_start=period_start,
            period_end=period_end,
            defaults={
                "value": value,
                "is_calculated": True,
                "entered_by": None,
                "notes": "Computed by KPI engine",
                "metadata": metadata,
            },
        )

        return {
            "id": str(entry.id),
            "kpi_id": str(kpi.id),
            "period_start": entry.period_start.isoformat(),
            "period_end": entry.period_end.isoformat(),
            "value": str(entry.value),
            "created": created,
            "metadata": entry.metadata,
        }

    def list_snapshots(
        self,
        tenant: TenantContext,
        *,
        kpi_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        kpi = self._get_tenant_kpi(tenant, kpi_id)
        queryset = KPIEntry.objects.filter(kpi=kpi).order_by("-period_start", "-created_at")

        if start_date:
            queryset = queryset.filter(period_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(period_end__lte=end_date)

        return [
            {
                "id": str(item.id),
                "kpi_id": str(item.kpi_id),
                "period_start": item.period_start.isoformat(),
                "period_end": item.period_end.isoformat(),
                "value": str(item.value),
                "metadata": item.metadata,
            }
            for item in queryset
        ]

    def _get_tenant_kpi(self, tenant: TenantContext, kpi_id: str) -> KPI:
        kpi = KPI.objects.filter(id=kpi_id).select_related("organization").first()
        if not kpi or str(kpi.organization_id) != str(tenant.organization_id):
            raise TenantIsolationError("KPI is outside the tenant scope.")
        return kpi

    def _to_date(self, value: date | str) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(value)
