from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.expense_accounting.constants import IK_REIMBURSEMENT, IK_REIMBURSEMENT_PAYMENT, SOURCE_MODULE
from apps.expense_accounting.exceptions import ExpenseApprovalError, ExpenseStatusError
from apps.expense_accounting.models import ExpenseApproval, ExpenseTransaction
from apps.expense_accounting.services.expense_approval_service import approve_expense, reject_expense
from apps.ledgers.models import Account
from apps.ledgers.services.audit_service import emit_audit_log
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal
from apps.ledgers.utils.periods import ensure_date_in_open_period


@transaction.atomic
def submit_employee_claim(
    *,
    expense: ExpenseTransaction,
    submitted_by_id: UUID,
) -> ExpenseTransaction:
    """Submit an employee reimbursement claim for approval."""
    if expense.status != ExpenseTransaction.Status.DRAFT:
        raise ExpenseStatusError("Only DRAFT expenses can be submitted.")
    if expense.employee is None:
        raise ExpenseStatusError("Employee reimbursement requires an employee reference.")

    expense.status = ExpenseTransaction.Status.SUBMITTED
    expense.save(update_fields=["status", "updated_at"])

    from apps.expense_accounting.services.expense_approval_service import route_for_approval
    route_for_approval(expense=expense)

    emit_audit_log(
        event_type="reimbursement.submitted",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=submitted_by_id,
        payload={"amount_ugx": str(expense.base_amount)},
    )
    return expense


def approve_claim(*, expense_id: UUID, approver_id: UUID, remarks: str = "") -> ExpenseTransaction:
    """Approve an employee reimbursement claim. Delegates to the standard approval service."""
    return approve_expense(expense_id=expense_id, approver_id=approver_id, remarks=remarks)


def reject_claim(*, expense_id: UUID, approver_id: UUID, remarks: str = "") -> ExpenseTransaction:
    """Reject an employee reimbursement claim."""
    return reject_expense(expense_id=expense_id, approver_id=approver_id, remarks=remarks)


@transaction.atomic
def reimburse_employee(
    *,
    expense: ExpenseTransaction,
    payment_date: date,
    cash_account: Account,
    reimbursement_liability_account: Account,
    paid_by_id: UUID | None = None,
) -> dict:
    """Settle an approved employee reimbursement claim.

    Posting:
        DR Employee Reimbursement Liability
        CR Cash / Bank

    Returns:
        dict with journal_id.
    """
    if expense.status != ExpenseTransaction.Status.POSTED:
        raise ExpenseStatusError("Expense must be POSTED before settlement.")
    if expense.payment_status == ExpenseTransaction.PaymentStatus.PAID:
        raise ExpenseStatusError("Expense has already been settled.")

    ensure_date_in_open_period(posting_date=payment_date, branch=expense.branch)

    journal = create_and_post_journal(
        reference=f"REIMB-PAY-{expense.reference}",
        journal_type="reimbursement_payment",
        posting_date=payment_date,
        description=f"Employee reimbursement settlement — {expense.description}",
        source_module=SOURCE_MODULE,
        source_id=str(expense.id),
        branch=expense.branch,
        created_by_id=paid_by_id,
        idempotency_key=f"{IK_REIMBURSEMENT_PAYMENT}:{expense.id}",
        transaction_currency_code=expense.currency.code,
        lines=build_two_line_entry(
            debit_account_id=reimbursement_liability_account.id,
            credit_account_id=cash_account.id,
            amount=expense.amount,
            currency=expense.currency.code,
            description=f"Reimbursement settlement — {expense.description}",
            branch=expense.branch,
            party_type="employee",
            party_id=str(expense.employee),
            exchange_rate=expense.exchange_rate,
        ),
    )

    expense.payment_status = ExpenseTransaction.PaymentStatus.PAID
    expense.status = ExpenseTransaction.Status.PAID
    expense.save(update_fields=["payment_status", "status", "updated_at"])

    emit_audit_log(
        event_type="reimbursement.settled",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=paid_by_id,
        payload={"amount_ugx": str(expense.base_amount), "payment_date": str(payment_date)},
    )
    return {"journal_id": str(journal.id)}
