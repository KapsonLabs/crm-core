from django.test import SimpleTestCase

from apps.kpis.application.contracts import TenantContext
from apps.kpis.infrastructure.compiler import SimpleDslSqlCompiler


class SimpleDslSqlCompilerTests(SimpleTestCase):
    def test_compiles_with_tenant_predicate(self):
        compiler = SimpleDslSqlCompiler()
        tenant = TenantContext(organization_id="org-1")

        formula = 'SUM(disbursement.amount WHERE project.status="active") / COUNT(beneficiaries.id)'
        compiled = compiler.compile_to_sql_template(tenant, formula)

        self.assertIn("organization_id = %(tenant_id)s", compiled["sql"])
        self.assertIn("SELECT", compiled["sql"])
        self.assertEqual(compiled["params"]["tenant_id"], "org-1")
        self.assertEqual(compiled["params"]["p1"], "active")
