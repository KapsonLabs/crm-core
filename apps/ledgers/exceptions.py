class AccountingError(Exception):
    """Base exception for the accounting engine."""


class FiscalPeriodClosedError(AccountingError):
    """Raised when posting is attempted into a closed fiscal period."""


class JournalBalanceError(AccountingError):
    """Raised when journal lines do not satisfy double entry."""


class ImmutableLedgerError(AccountingError):
    """Raised when append-only ledger data is mutated."""


class PostingConfigurationError(AccountingError):
    """Raised when a posting flow is missing account mappings or setup."""


class ReconciliationError(AccountingError):
    """Raised when reconciliation operations fail validation."""
