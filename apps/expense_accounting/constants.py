from __future__ import annotations

from decimal import Decimal

ZERO = Decimal("0.00")
TWO_DP = Decimal("0.01")

# Approval thresholds in UGX base currency
MANAGER_APPROVAL_LIMIT = Decimal("500000")
FINANCE_APPROVAL_LIMIT = Decimal("5000000")

# Ordered list: (upper_limit_ugx_or_None, level_int, label)
APPROVAL_THRESHOLDS = [
    (MANAGER_APPROVAL_LIMIT, 1, "manager"),
    (FINANCE_APPROVAL_LIMIT, 2, "finance"),
    (None, 3, "cfo"),
]

SOURCE_MODULE = "expense_accounting"

# Idempotency key prefixes
IK_EXPENSE = "expense"
IK_EXPENSE_PAYMENT = "expense-payment"
IK_EXPENSE_REVERSAL = "expense-reversal"
IK_REIMBURSEMENT = "reimbursement"
IK_REIMBURSEMENT_PAYMENT = "reimbursement-payment"
IK_PREPAID_INITIAL = "prepaid-initial"
IK_PREPAID_AMORTIZATION = "prepaid-amort"
IK_ACCRUAL_EXPENSE = "expense-accrual"

# Escalation grace period (days before escalation)
ESCALATION_DAYS = 2
