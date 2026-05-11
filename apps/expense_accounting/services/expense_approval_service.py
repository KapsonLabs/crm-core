from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.expense_accounting.constants import APPROVAL_THRESHOLDS
from apps.expense_accounting.exceptions import ExpenseApprovalError, ExpenseStatusError
from apps.expense_accounting.models import ExpenseApproval, ExpenseTransaction
from apps.ledgers.services.audit_service import emit_audit_log


def determine_approval_level(*, base_amount_ugx: Decimal) -> tuple[int, str]:
    """Return the first approval level required for this amount.

    Returns (level_int, label).
    """
    for limit, level, label in APPROVAL_THRESHOLDS:
        if limit is None or base_amount_ugx <= limit:
            return level, label
    return 3, "cfo"


def _next_required_level(expense: ExpenseTransaction) -> int | None:
    """Return the next pending approval level, or None if all complete."""
    required_level, _ = determine_approval_level(base_amount_ugx=expense.base_amount)
    completed = set(
        ExpenseApproval.objects.filter(
            expense_transaction=expense,
            status=ExpenseApproval.Status.APPROVED,
        ).values_list("approval_level", flat=True)
    )
    for _, level, _ in APPROVAL_THRESHOLDS:
        if level > required_level:
            break
        if level not in completed:
            return level
    return None


@transaction.atomic
def route_for_approval(*, expense: ExpenseTransaction) -> ExpenseApproval:
    """Create the first pending ExpenseApproval for an expense."""
    if expense.status != ExpenseTransaction.Status.SUBMITTED:
        raise ExpenseStatusError("Expense must be in SUBMITTED state to route for approval.")
    level, _ = determine_approval_level(base_amount_ugx=expense.base_amount)
    approval = ExpenseApproval.objects.create(
        expense_transaction=expense,
        approval_level=level,
        status=ExpenseApproval.Status.PENDING,
    )
    emit_audit_log(
        event_type="expense.routed_for_approval",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=None,
        payload={"approval_level": level, "approval_id": str(approval.id)},
    )
    return approval


@transaction.atomic
def approve_expense(*, expense_id: UUID, approver_id: UUID, remarks: str = "") -> ExpenseTransaction:
    """Approve the current pending level; route to next or mark fully approved."""
    expense = ExpenseTransaction.objects.select_for_update().get(id=expense_id)
    if expense.status not in (ExpenseTransaction.Status.SUBMITTED,):
        raise ExpenseStatusError("Expense is not in a state that can be approved.")

    try:
        approval = ExpenseApproval.objects.select_for_update().get(
            expense_transaction=expense,
            status=ExpenseApproval.Status.PENDING,
        )
    except ExpenseApproval.DoesNotExist:
        raise ExpenseApprovalError("No pending approval record found for this expense.")

    approval.status = ExpenseApproval.Status.APPROVED
    approval.approver = approver_id
    approval.approved_at = datetime.now(tz=timezone.utc)
    approval.remarks = remarks
    approval.save(update_fields=["status", "approver", "approved_at", "remarks"])

    next_level = _next_required_level(expense)
    if next_level is not None:
        ExpenseApproval.objects.create(
            expense_transaction=expense,
            approval_level=next_level,
            status=ExpenseApproval.Status.PENDING,
        )
    else:
        expense.approval_status = ExpenseTransaction.ApprovalStatus.APPROVED
        expense.status = ExpenseTransaction.Status.APPROVED
        expense.approved_by = approver_id
        expense.save(update_fields=["approval_status", "status", "approved_by", "updated_at"])

    emit_audit_log(
        event_type="expense.approved",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=approver_id,
        payload={"approval_level": approval.approval_level, "remarks": remarks},
    )
    return expense


@transaction.atomic
def reject_expense(*, expense_id: UUID, approver_id: UUID, remarks: str = "") -> ExpenseTransaction:
    """Reject the expense at the current approval level."""
    expense = ExpenseTransaction.objects.select_for_update().get(id=expense_id)
    try:
        approval = ExpenseApproval.objects.select_for_update().get(
            expense_transaction=expense,
            status=ExpenseApproval.Status.PENDING,
        )
    except ExpenseApproval.DoesNotExist:
        raise ExpenseApprovalError("No pending approval record found for this expense.")

    approval.status = ExpenseApproval.Status.REJECTED
    approval.approver = approver_id
    approval.approved_at = datetime.now(tz=timezone.utc)
    approval.remarks = remarks
    approval.save(update_fields=["status", "approver", "approved_at", "remarks"])

    expense.approval_status = ExpenseTransaction.ApprovalStatus.REJECTED
    expense.status = ExpenseTransaction.Status.REJECTED
    expense.save(update_fields=["approval_status", "status", "updated_at"])

    emit_audit_log(
        event_type="expense.rejected",
        entity_type="ExpenseTransaction",
        entity_id=expense.id,
        branch=expense.branch,
        performed_by_id=approver_id,
        payload={"approval_level": approval.approval_level, "remarks": remarks},
    )
    return expense


@transaction.atomic
def escalate_pending_approval(*, expense_id: UUID) -> ExpenseApproval | None:
    """Mark overdue pending approval as escalated. Called by Celery task."""
    try:
        approval = ExpenseApproval.objects.select_for_update().get(
            expense_transaction_id=expense_id,
            status=ExpenseApproval.Status.PENDING,
        )
    except ExpenseApproval.DoesNotExist:
        return None
    approval.status = ExpenseApproval.Status.ESCALATED
    approval.escalated_at = datetime.now(tz=timezone.utc)
    approval.save(update_fields=["status", "escalated_at"])
    emit_audit_log(
        event_type="expense.approval_escalated",
        entity_type="ExpenseTransaction",
        entity_id=expense_id,
        branch=None,
        performed_by_id=None,
        payload={"approval_id": str(approval.id), "level": approval.approval_level},
    )
    return approval
