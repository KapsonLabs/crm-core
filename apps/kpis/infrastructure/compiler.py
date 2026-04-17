import re
from typing import Any

from apps.kpis.application.contracts import FormulaCompiler, TenantContext
from apps.kpis.domain.exceptions import FormulaCompilationError

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FUNCTION_RE = re.compile(r"^(SUM|COUNT|AVG|MIN|MAX)\((.*)\)$", re.IGNORECASE)
_MEASURE_RE = re.compile(
    r"^(?P<table>[A-Za-z_][A-Za-z0-9_]*)\.(?P<column>[A-Za-z_][A-Za-z0-9_]*)(?:\s+WHERE\s+(?P<where>.+))?$",
    re.IGNORECASE,
)
_FILTER_RE = re.compile(
    r"^(?P<field>(?:[A-Za-z_][A-Za-z0-9_]*\.)?[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\"(?P<value>[^\"]*)\"$",
    re.IGNORECASE,
)


class SimpleDslSqlCompiler(FormulaCompiler):
    """Compiles a constrained KPI DSL into parameterized SQL."""

    def __init__(self) -> None:
        self._param_index = 0

    def compile_to_sql_template(self, tenant: TenantContext, formula: str) -> dict[str, Any]:
        if not formula or not formula.strip():
            raise FormulaCompilationError("Formula is required for SQL compilation.")

        self._param_index = 0
        expr = formula.strip()
        sql_expr, params, tables = self._compile_expression(expr, tenant.organization_id)
        return {
            "sql": f"SELECT {sql_expr} AS value",
            "params": params,
            "metadata": {"tables": sorted(tables)},
        }

    def _compile_expression(
        self,
        expr: str,
        tenant_id: str,
    ) -> tuple[str, dict[str, Any], set[str]]:
        expr = self._strip_outer_parens(expr.strip())

        for op in ("+", "-"):
            parts = self._split_top_level(expr, op)
            if parts:
                left_sql, left_params, left_tables = self._compile_expression(parts[0], tenant_id)
                right_sql, right_params, right_tables = self._compile_expression(parts[1], tenant_id)
                return (
                    f"({left_sql}) {op} ({right_sql})",
                    {**left_params, **right_params},
                    left_tables | right_tables,
                )

        for op in ("*", "/"):
            parts = self._split_top_level(expr, op)
            if parts:
                left_sql, left_params, left_tables = self._compile_expression(parts[0], tenant_id)
                right_sql, right_params, right_tables = self._compile_expression(parts[1], tenant_id)
                if op == "/":
                    sql = f"({left_sql}) / NULLIF(({right_sql}), 0)"
                else:
                    sql = f"({left_sql}) * ({right_sql})"
                return sql, {**left_params, **right_params}, left_tables | right_tables

        if re.fullmatch(r"\d+(?:\.\d+)?", expr):
            return expr, {}, set()

        return self._compile_function(expr, tenant_id)

    def _compile_function(self, atom: str, tenant_id: str) -> tuple[str, dict[str, Any], set[str]]:
        match = _FUNCTION_RE.match(atom.strip())
        if not match:
            raise FormulaCompilationError(
                "Unsupported DSL expression. Expected aggregate functions like SUM(table.column WHERE field=\"value\")."
            )

        func_name = match.group(1).upper()
        body = match.group(2).strip()
        body_match = _MEASURE_RE.match(body)
        if not body_match:
            raise FormulaCompilationError(f"Invalid function body: '{body}'.")

        table = body_match.group("table")
        column = body_match.group("column")
        self._validate_identifier(table)
        self._validate_identifier(column)

        where_clauses = [f"{table}.organization_id = %(tenant_id)s"]
        params: dict[str, Any] = {"tenant_id": tenant_id}

        where_expr = body_match.group("where")
        if where_expr:
            field_sql, filter_params = self._compile_filter(where_expr.strip(), default_table=table)
            where_clauses.append(field_sql)
            params.update(filter_params)

        where_sql = " AND ".join(where_clauses)
        sql = (
            "(SELECT COALESCE({func}({table}.{column}), 0) "
            "FROM {table} WHERE {where_sql})"
        ).format(func=func_name, table=table, column=column, where_sql=where_sql)
        return sql, params, {table}

    def _compile_filter(self, filter_expr: str, default_table: str) -> tuple[str, dict[str, Any]]:
        match = _FILTER_RE.match(filter_expr)
        if not match:
            raise FormulaCompilationError(f"Unsupported filter clause: '{filter_expr}'.")

        field = match.group("field")
        if "." in field:
            table, column = field.split(".", 1)
        else:
            table, column = default_table, field

        self._validate_identifier(table)
        self._validate_identifier(column)

        param_name = self._new_param()
        return f"{table}.{column} = %({param_name})s", {param_name: match.group("value")}

    def _new_param(self) -> str:
        self._param_index += 1
        return f"p{self._param_index}"

    def _validate_identifier(self, name: str) -> None:
        if not _IDENTIFIER_RE.fullmatch(name):
            raise FormulaCompilationError(f"Invalid identifier '{name}'.")

    def _split_top_level(self, expr: str, op: str) -> tuple[str, str] | None:
        depth = 0
        for idx in range(len(expr) - 1, -1, -1):
            ch = expr[idx]
            if ch == ")":
                depth += 1
            elif ch == "(":
                depth -= 1
            elif ch == op and depth == 0:
                return expr[:idx].strip(), expr[idx + 1 :].strip()
        return None

    def _strip_outer_parens(self, expr: str) -> str:
        if not expr or expr[0] != "(" or expr[-1] != ")":
            return expr

        depth = 0
        for idx, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and idx != len(expr) - 1:
                    return expr
        return expr[1:-1].strip()
