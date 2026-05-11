from __future__ import annotations


class ExpenseError(Exception):
    """Base exception for all expense accounting failures."""


class ExpenseStatusError(ExpenseError):
    """Raised when an action is attempted in the wrong lifecycle state."""


class ExpenseApprovalError(ExpenseError):
    """Raised when an approval workflow constraint is violated."""


class BudgetExceededError(ExpenseError):
    """Raised when posting would exceed an approved budget allocation."""


class BudgetNotFoundError(ExpenseError):
    """Raised when no budget exists for the given dimension combination."""


class PrepaidScheduleError(ExpenseError):
    """Raised when prepaid amortization state is invalid."""


class ExpenseConfigurationError(ExpenseError):
    """Raised when required account configuration is missing."""


class AllocationError(ExpenseError):
    """Raised when allocation percentages do not sum to 100."""
