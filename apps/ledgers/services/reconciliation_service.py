from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Sum

from apps.ledgers.exceptions import ReconciliationError
from apps.ledgers.models import ControlAccount, JournalLine, LedgerEntry, SubLedgerAccount, SubLedgerEntry
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.types import BankStatementLine


@transaction.atomic
def auto_match_transactions(*, bank_account_id: UUID, statement_lines: list[BankStatementLine], branch: UUID | None = None) -> list[dict]:
    matches = []
    for statement_line in statement_lines:
        candidate = (
            JournalLine.objects.filter(
                account_id=bank_account_id,
                branch=branch,
                journal_entry__status="posted",
                journal_entry__date=statement_line.transaction_date,
            )
            .filter(debit=statement_line.amount)
            .select_related("journal_entry")
            .first()
        )
        if candidate:
            matches.append(
                {
                    "statement_reference": statement_line.reference,
                    "journal_entry_id": str(candidate.journal_entry_id),
                    "journal_line_id": str(candidate.id),
                }
            )
    return matches


@transaction.atomic
def reconcile_bank_statement(
    *,
    bank_account_id: UUID,
    statement_lines: list[BankStatementLine],
    branch: UUID | None = None,
    performed_by_id: UUID | None = None,
    require_full_match: bool = False,
) -> dict:
    matches = auto_match_transactions(
        bank_account_id=bank_account_id,
        statement_lines=statement_lines,
        branch=branch,
    )
    matched_refs = {m["statement_reference"] for m in matches}
    unmatched = [sl for sl in statement_lines if sl.reference not in matched_refs]
    if require_full_match and unmatched:
        raise ReconciliationError(
            f"Reconciliation incomplete: {len(unmatched)} statement line(s) could not be auto-matched."
        )
    emit_audit_log(
        event_type="reconciliation.completed",
        entity_type="Account",
        entity_id=bank_account_id,
        branch=branch,
        performed_by_id=performed_by_id,
        payload={
            "matched_count": len(matches),
            "unmatched_count": len(unmatched),
            "total_lines": len(statement_lines),
        },
    )
    return {
        "matched": matches,
        "unmatched": [{"reference": sl.reference, "amount": str(sl.amount), "date": str(sl.transaction_date)} for sl in unmatched],
        "matched_count": len(matches),
        "unmatched_count": len(unmatched),
        "is_fully_reconciled": len(unmatched) == 0,
    }


def _control_account_balance(*, control_account: ControlAccount, branch: UUID | None = None) -> Decimal:
    queryset = LedgerEntry.objects.filter(account=control_account.gl_account)
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    totals = queryset.aggregate(
        debit_total=Sum("debit_base", default=Decimal("0.00")),
        credit_total=Sum("credit_base", default=Decimal("0.00")),
    )
    if control_account.gl_account.normal_balance == "debit":
        return totals["debit_total"] - totals["credit_total"]
    return totals["credit_total"] - totals["debit_total"]


def _subledger_total(*, control_account: ControlAccount, branch: UUID | None = None) -> Decimal:
    queryset = SubLedgerEntry.objects.filter(subledger_account__parent_control_account=control_account)
    if branch is not None:
        queryset = queryset.filter(branch=branch)
    totals = queryset.aggregate(
        debit_total=Sum("debit_base", default=Decimal("0.00")),
        credit_total=Sum("credit_base", default=Decimal("0.00")),
    )
    if control_account.gl_account.normal_balance == "debit":
        return totals["debit_total"] - totals["credit_total"]
    return totals["credit_total"] - totals["debit_total"]


def reconcile_control_accounts(*, branch: UUID | None = None) -> list[dict]:
    results = []
    controls = ControlAccount.objects.filter(is_active=True)
    if branch is not None:
        controls = controls.filter(branch=branch)
    for control in controls.select_related("gl_account"):
        gl_balance = _control_account_balance(control_account=control, branch=branch)
        subledger_balance = _subledger_total(control_account=control, branch=branch)
        results.append(
            {
                "control_account_id": str(control.id),
                "control_account_code": control.code,
                "gl_balance": gl_balance,
                "subledger_balance": subledger_balance,
                "difference": gl_balance - subledger_balance,
                "is_balanced": gl_balance == subledger_balance,
            }
        )
    return results


def validate_subledger_integrity(*, branch: UUID | None = None) -> dict:
    results = reconcile_control_accounts(branch=branch)
    failures = [row for row in results if not row["is_balanced"]]
    return {"is_valid": not failures, "results": results, "failures": failures}


def detect_out_of_balance_subledgers(*, branch: UUID | None = None) -> list[dict]:
    controls = reconcile_control_accounts(branch=branch)
    return [row for row in controls if not row["is_balanced"]]
