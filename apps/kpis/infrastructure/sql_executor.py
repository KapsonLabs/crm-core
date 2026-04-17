from typing import Any

from django.db import connection


class DjangoSqlExecutor:
    """Executes parameterized SQL using Django DB connection."""

    def execute(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            if not cursor.description:
                return []
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
