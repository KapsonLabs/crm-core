from __future__ import annotations

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.models import Account, AccountingConfiguration, Currency


DEFAULT_CHART_OF_ACCOUNTS = [
    ("1100", "Inventory Asset", "asset", "inventory_asset"),
    ("1110", "Inventory Adjustment", "expense", "inventory_adjustment"),
    ("1115", "Inventory Variance", "expense", "inventory_variance"),
    ("5100", "COGS", "expense", "cogs"),
    ("2105", "Purchase Clearing", "liability", "purchase_clearing"),
    ("4100", "Sales Revenue", "income", "sales_revenue"),
    ("1120", "Manufacturing WIP", "asset", "manufacturing_wip"),
    ("1130", "Inventory In Transit", "asset", "inventory_in_transit"),
    ("1140", "Inventory Provision", "liability", "inventory_provision"),
    ("5105", "Inventory Write-down Expense", "expense", "inventory_write_down_expense"),
    ("4105", "Inventory Recovery Income", "income", "inventory_recovery_income"),
    ("2415", "Inventory GRNI", "liability", "inventory_grni"),
    ("4200", "Rental Income", "income", "rental_income"),
    ("2200", "Deferred Rental Income", "liability", "deferred_rental_income"),
    ("2210", "Security Deposit Liability", "liability", "security_deposit_liability"),
    ("1200", "Rental Receivables", "asset", "rental_receivables"),
    ("2300", "Member Savings", "liability", "member_savings"),
    ("1210", "Loan Receivables", "asset", "loan_receivables"),
    ("4300", "Interest Income", "income", "interest_income"),
    ("1220", "Interest Receivable", "asset", "interest_receivable"),
    ("4310", "Penalty Income", "income", "penalty_income"),
    ("2310", "Dividend Payable", "liability", "dividend_payable"),
    ("1230", "Accounts Receivable", "asset", "accounts_receivable"),
    ("5200", "Bad Debt Expense", "expense", "bad_debt_expense"),
    ("1240", "Allowance for Doubtful Accounts", "asset", "allowance_for_doubtful_accounts"),
    ("2400", "Accounts Payable", "liability", "accounts_payable"),
    ("2410", "Accrued Expenses", "liability", "accrued_expenses"),
    ("2420", "Expense Clearing", "liability", "expense_clearing"),
    ("1500", "Fixed Assets", "asset", "fixed_assets"),
    ("1510", "Accumulated Depreciation", "asset", "accumulated_depreciation"),
    ("5300", "Depreciation Expense", "expense", "depreciation_expense"),
    ("4320", "Asset Disposal Gain/Loss", "income", "asset_disposal_gain_loss"),
    ("1000", "Cash and Cash Equivalent Control", "asset", "cash_and_cash_equivalent_control"),
    ("1010", "Electronic Money Control", "asset", "electronic_money_control"),
    ("1250", "Staff Receivable Control", "asset", "staff_receivable_control"),
    ("2430", "Payroll Payable Control", "liability", "payroll_payable_control"),
    ("1135", "Work In Progress Control", "asset", "work_in_progress_control"),
    ("4108", "Project Revenue Control", "income", "project_revenue_control"),
    ("5108", "Project Cost Control", "expense", "project_cost_control"),
    ("1136", "Material Consumption Control", "asset", "material_consumption_control"),
    ("5110", "Production Variance Control", "expense", "production_variance_control"),
    ("1145", "Consignment Inventory Control", "asset", "consignment_inventory_control"),
    ("2440", "Consignment Payable Control", "liability", "consignment_payable_control"),
    ("1260", "Intercompany Control Account", "asset", "intercompany_control_account"),
    ("1270", "VAT Input Control", "asset", "vat_input_control"),
    ("2450", "VAT Output Control", "liability", "vat_output_control"),
    ("2460", "Withholding Tax Control", "liability", "withholding_tax_control"),
    ("2470", "Loan Liability Control", "liability", "loan_liability_control"),
    ("2480", "Interest Payable Control", "liability", "interest_payable_control"),
    ("2490", "Loan Penalty Control", "liability", "loan_penalty_control"),
    ("4330", "Forex Gain", "income", "forex_gain"),
    ("5400", "Forex Loss", "expense", "forex_loss"),
    ("4331", "Unrealized Forex Gain", "income", "unrealized_forex_gain"),
    ("5401", "Unrealized Forex Loss", "expense", "unrealized_forex_loss"),
    # Expense accounting accounts
    ("1300", "Prepaid Expenses", "asset", "prepaid_expenses"),
    ("5500", "Operating Expenses", "expense", "operating_expenses"),
    ("2500", "Employee Reimbursement Liability", "liability", "employee_reimbursement_liability"),
    ("2510", "Corporate Card Clearing", "liability", "corporate_card_clearing"),
    ("2520", "Accrued Expense Provision", "liability", "accrued_expense_provision"),
    ("5501", "Department Expense Control", "expense", "department_expense_control"),
]

CONTROL_ACCOUNT_CATEGORIES = {
    "inventory_asset",
    "accounts_receivable",
    "accounts_payable",
    "fixed_assets",
    "accumulated_depreciation",
    "member_savings",
    "loan_receivables",
    "cash_and_cash_equivalent_control",
    "electronic_money_control",
    "staff_receivable_control",
    "payroll_payable_control",
    "work_in_progress_control",
    "project_revenue_control",
    "project_cost_control",
    "manufacturing_wip",
    "material_consumption_control",
    "production_variance_control",
    "consignment_inventory_control",
    "consignment_payable_control",
    "intercompany_control_account",
    "vat_input_control",
    "vat_output_control",
    "withholding_tax_control",
    "loan_liability_control",
    "interest_payable_control",
    "loan_penalty_control",
}

# Accounts that REQUIRE a SubLedgerAccount reference on every posting.
# Inventory uses a separate InventoryJournalEntry system, so inventory_asset
# and other inventory accounts are excluded — they allow direct GL posting.
RESTRICTED_CONTROL_ACCOUNT_CATEGORIES = {
    "accounts_receivable",
    "accounts_payable",
    "member_savings",
    "loan_receivables",
    "interest_receivable",
    "staff_receivable_control",
    "payroll_payable_control",
    "loan_liability_control",
    "interest_payable_control",
    "loan_penalty_control",
    "consignment_payable_control",
}


def seed_default_chart_of_accounts(*, branch=None, currency: str = DEFAULT_CURRENCY):
    base_currency, _ = Currency.objects.get_or_create(
        code=DEFAULT_CURRENCY,
        defaults={
            "name": "Ugandan Shilling",
            "symbol": "UGX",
            "decimal_places": 0,
            "is_base_currency": True,
            "is_active": True,
        },
    )
    if currency != DEFAULT_CURRENCY:
        Currency.objects.get_or_create(
            code=currency,
            defaults={
                "name": currency,
                "symbol": currency,
                "decimal_places": 2,
                "is_active": True,
            },
        )
    config, _ = AccountingConfiguration.objects.get_or_create(
        branch=branch,
        defaults={
            "base_currency": base_currency,
            "default_accounts": {},
        },
    )
    account_map = {}
    for code, name, account_type, category in DEFAULT_CHART_OF_ACCOUNTS:
        is_control = category in CONTROL_ACCOUNT_CATEGORIES
        # Restricted controls require a SubLedgerAccount on every posting.
        # Inventory / manufacturing accounts use a separate InventoryJournal
        # system and can be posted to directly at the GL level.
        is_restricted = category in RESTRICTED_CONTROL_ACCOUNT_CATEGORIES
        account, _ = Account.objects.get_or_create(
            code=code,
            branch=branch,
            defaults={
                "name": name,
                "account_type": account_type,
                "category": category,
                "currency": base_currency,
                "allows_manual_posting": not is_restricted,
                "is_control_account": is_control,
            },
        )
        account_map[category] = account.code
    account_map["forex_gain"] = "4330"
    account_map["forex_loss"] = "5400"
    account_map["unrealized_forex_gain"] = "4331"
    account_map["unrealized_forex_loss"] = "5401"
    config.default_accounts = {**config.default_accounts, **account_map}
    config.save(update_fields=["default_accounts", "updated_at"])
    return config
