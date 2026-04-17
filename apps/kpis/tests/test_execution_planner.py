from django.test import SimpleTestCase

from apps.kpis.application.contracts import TenantContext
from apps.kpis.execution.planner import DefaultExecutionPlanner


class DefaultExecutionPlannerTests(SimpleTestCase):
    def test_builds_idempotency_key(self):
        planner = DefaultExecutionPlanner()
        tenant = TenantContext(organization_id="org-1")

        plan = planner.build_plan(
            tenant_ctx=tenant,
            kpi_id="kpi-1",
            kpi_version={"version": 3},
            period_spec={"kind": "monthly", "start": "2026-01-01", "end": "2026-01-31"},
        )

        self.assertEqual(plan["window"]["kind"], "monthly")
        self.assertEqual(plan["window"]["start"].isoformat(), "2026-01-01")
        self.assertTrue(plan["idempotency_key"])
