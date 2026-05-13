from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import transaction

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.exceptions import PostingConfigurationError
from apps.ledgers.models import Account, ControlAccount, Currency, SubLedgerAccount
from apps.ledgers.repositories.account_repository import AccountRepository


ENTITY_CONTROL_ACCOUNT_MAP = {
    "product": [
        ("inventory_asset", "INV", "Inventory Asset Ledger"),
        ("inventory_adjustment", "INVADJ", "Inventory Adjustment Ledger"),
        ("cogs", "COGS", "COGS Ledger"),
        ("inventory_variance", "INVVAR", "Inventory Variance Ledger"),
    ],
    "customer": [("accounts_receivable", "AR-CUST", "Customer Receivable Ledger")],
    "supplier": [("accounts_payable", "AP-SUP", "Supplier Payable Ledger")],
    "fixed_asset": [
        ("fixed_assets", "FA", "Asset Cost Ledger"),
        ("accumulated_depreciation", "FA-AD", "Accumulated Depreciation Ledger"),
        ("depreciation_expense", "FA-DE", "Depreciation Expense Ledger"),
        ("asset_disposal_gain_loss", "FA-DISP", "Asset Disposal Ledger"),
    ],
    "bank_account": [("cash_and_cash_equivalent_control", "BANK", "Bank Ledger")],
    "wallet": [("electronic_money_control", "WAL", "Wallet Ledger")],
    "warehouse": [
        ("inventory_asset", "WH", "Warehouse Inventory Ledger"),
        ("inventory_variance", "WHVAR", "Warehouse Variance Ledger"),
    ],
    "sacco_member": [
        ("member_savings", "SAV", "Member Savings Ledger"),
        ("loan_receivables", "LOAN", "Member Loan Ledger"),
        ("interest_receivable", "INT", "Member Interest Ledger"),
    ],
    "employee": [
        ("staff_receivable_control", "EMP-ADV", "Employee Advance Ledger"),
        ("payroll_payable_control", "EMP-PAY", "Payroll Liability Ledger"),
    ],
    "project": [
        ("work_in_progress_control", "PRJ-WIP", "WIP Ledger"),
        ("project_cost_control", "PRJ-COST", "Project Cost Ledger"),
        ("project_revenue_control", "PRJ-REV", "Project Revenue Ledger"),
    ],
    "work_order": [
        ("manufacturing_wip", "WO-WIP", "WIP Ledger"),
        ("material_consumption_control", "WO-MAT", "Material Consumption Ledger"),
        ("production_variance_control", "WO-VAR", "Production Variance Ledger"),
    ],
    "consignment_partner": [
        ("consignment_inventory_control", "CON-INV", "Consignment Inventory Ledger"),
        ("consignment_payable_control", "CON-PAY", "Consignment Settlement Ledger"),
    ],
    "branch_entity": [
        ("intercompany_control_account", "BR-REC", "Interbranch Receivable Ledger"),
        ("intercompany_control_account", "BR-PAY", "Interbranch Payable Ledger"),
        ("intercompany_control_account", "BR-CLR", "Branch Clearing Ledger"),
    ],
    "tax_authority": [
        ("vat_input_control", "VAT-IN", "VAT Input Ledger"),
        ("vat_output_control", "VAT-OUT", "VAT Output Ledger"),
        ("withholding_tax_control", "WHT", "Withholding Tax Ledger"),
    ],
    "loan_facility": [
        ("loan_liability_control", "LN-PRN", "Loan Principal Ledger"),
        ("interest_payable_control", "LN-INT", "Loan Interest Ledger"),
        ("loan_penalty_control", "LN-PEN", "Loan Penalty Ledger"),
    ],
}


@dataclass(frozen=True)
class EntitySubledgerRequest:
    entity_type: str
    entity_id: str
    entity_name: str
    branch: UUID | None
    currency_code: str = DEFAULT_CURRENCY


def generate_subledger_code(*, prefix: str, entity_reference: str) -> str:
    return f"{prefix}-{entity_reference}".upper()


def assign_control_account(*, control_account_key: str, branch: UUID | None) -> ControlAccount:
    try:
        config = AccountRepository.get_configuration(branch)
    except Exception as exc:
        raise PostingConfigurationError(
            f"No AccountingConfiguration found for branch={branch}. "
            "Run 'python manage.py seed_default_chart' first."
        ) from exc
    account_code = config.default_accounts.get(control_account_key, "")
    if not account_code:
        raise PostingConfigurationError(
            f"Account key '{control_account_key}' is not configured in default_accounts "
            f"(branch={branch}). Run 'python manage.py seed_default_chart' first."
        )
    try:
        gl_account = AccountRepository.get_by_code(code=account_code, branch=branch)
    except Account.DoesNotExist:
        raise PostingConfigurationError(
            f"GL account with code '{account_code}' (key '{control_account_key}') "
            f"does not exist for branch={branch}. Re-run 'python manage.py seed_default_chart'."
        )
    control, _ = ControlAccount.objects.get_or_create(
        gl_account=gl_account,
        defaults={
            "code": gl_account.code,
            "name": gl_account.name,
            "branch": branch,
            "currency": gl_account.currency,
            "allows_manual_posting": gl_account.allows_manual_posting,
        },
    )
    return control


@transaction.atomic
def create_entity_subledger(
    *,
    entity_type: str,
    entity_id: str,
    entity_name: str,
    ledger_purpose: str,
    control_account_key: str,
    code_prefix: str,
    branch: UUID | None,
    currency_code: str = DEFAULT_CURRENCY,
) -> SubLedgerAccount:
    control_account = assign_control_account(control_account_key=control_account_key, branch=branch)
    currency = AccountRepository.get_currency(currency_code)
    account_code = generate_subledger_code(prefix=code_prefix, entity_reference=entity_id)
    subledger, _ = SubLedgerAccount.objects.get_or_create(
        entity_type=entity_type,
        entity_id=entity_id,
        ledger_purpose=ledger_purpose,
        parent_control_account=control_account,
        defaults={
            "account_code": account_code,
            "account_name": f"{ledger_purpose}: {entity_name}",
            "branch": branch,
            "currency": currency,
            "gl_account": control_account.gl_account,
        },
    )
    return subledger


@transaction.atomic
def create_default_entity_accounts(*, request: EntitySubledgerRequest) -> list[SubLedgerAccount]:
    mappings = ENTITY_CONTROL_ACCOUNT_MAP.get(request.entity_type)
    if not mappings:
        raise PostingConfigurationError(f"No subledger mapping configured for entity type '{request.entity_type}'.")
    created = []
    for control_key, prefix, purpose in mappings:
        created.append(
            create_entity_subledger(
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                entity_name=request.entity_name,
                ledger_purpose=purpose,
                control_account_key=control_key,
                code_prefix=prefix,
                branch=request.branch,
                currency_code=request.currency_code,
            )
        )
    return created
