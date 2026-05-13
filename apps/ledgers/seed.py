from __future__ import annotations

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.models import Account, AccountingConfiguration, Currency


# ---------------------------------------------------------------------------
# Core accounts — seeded for every business type
# ---------------------------------------------------------------------------
#
# Account number ranges:
#   1000       Cash on Hand — physical cash at tills; owned by the "Cash" payment method
#   1001       Cash & Cash Equivalent Control — aggregation parent for bank/card accounts
#              REPORTING ONLY — allows_manual_posting=False; do not post directly to this account
#   1010       Electronic Money Control — aggregation parent for mobile money/wallet accounts
#              REPORTING ONLY — allows_manual_posting=False; do not post directly to this account
#
#   1050-1059  RESERVED — bank / direct-debit payment method accounts (auto-assigned)
#   1060-1069  RESERVED — card / POS payment method accounts (auto-assigned)
#   1070-1079  RESERVED — mobile money / wallet payment method accounts (auto-assigned)
#   1080-1089  RESERVED — cheque payment method accounts (auto-assigned)
#
#   These ranges are NOT seeded here. Each account in 1050-1089 is created
#   atomically when a PaymentMethod is created via create_payment_method().
#   The code generator (_next_payment_account_code) selects the next available
#   code within the appropriate range for the branch.
#
#   1100-1199  Receivables
#   1200-1299  Other current assets / prepayments
#   1300-1399  Inventory assets
#   1400-1499  Loan receivables (microfinance)
#   1500-1599  Fixed assets / PPE
#   1600-1699  Property assets (real estate)
#   2000-2099  Current payables
#   2100-2199  Tax & payroll liabilities
#   2200-2299  Inventory payables / clearing
#   2300-2399  Member liabilities (microfinance)
#   2400-2499  Long-term / control liabilities
#   2600-2699  Property liabilities (real estate)
#   3000-3099  Equity
#   3100-3199  Microfinance equity
#   3200-3299  Property equity (real estate)
#   4000-4099  Revenue (general services)
#   4100-4199  Inventory revenue
#   4200-4299  Interest & fee income (microfinance)
#   4300-4399  Forex / finance income
#   4400-4499  Rental & property income (real estate)
#   5000-5099  Direct / cost-of-sales expenses
#   5100-5199  Inventory direct costs
#   5200-5299  Loan expenses (microfinance)
#   5300-5399  Property expenses (real estate)
#   5400-5499  Forex / finance expense
#   6000-6099  Operating expenses
#
# Each tuple: (code, name, account_type, category, allows_manual_posting)
# allows_manual_posting defaults to True; set False for aggregation-only accounts.
# ---------------------------------------------------------------------------

CORE_ACCOUNTS = [
    # --- Cash & liquid assets ---
    # 1000: direct posting target for physical cash transactions.
    # 1001/1010: aggregation parents for payment method accounts; never posted to directly.
    ("1000", "Cash on Hand", "asset", "cash_on_hand"),
    ("1001", "Cash and Cash Equivalent Control", "asset", "cash_and_cash_equivalent_control"),
    ("1010", "Electronic Money Control", "asset", "electronic_money_control"),

    # --- Receivables ---
    ("1100", "Accounts Receivable", "asset", "accounts_receivable"),
    ("1105", "Allowance for Doubtful Accounts", "asset", "allowance_for_doubtful_accounts"),
    ("1110", "Staff Receivable Control", "asset", "staff_receivable_control"),
    ("1115", "Interest Receivable", "asset", "interest_receivable"),
    ("1120", "Intercompany Control Account", "asset", "intercompany_control_account"),

    # --- Prepayments & other current assets ---
    ("1200", "Prepaid Expenses", "asset", "prepaid_expenses"),
    ("1210", "VAT Input Control", "asset", "vat_input_control"),

    # --- Fixed assets ---
    ("1500", "Fixed Assets", "asset", "fixed_assets"),
    ("1505", "Accumulated Depreciation", "asset", "accumulated_depreciation"),

    # --- Current payables ---
    ("2000", "Accounts Payable", "liability", "accounts_payable"),
    ("2005", "Accrued Expenses", "liability", "accrued_expenses"),
    ("2010", "Purchase Clearing", "liability", "purchase_clearing"),
    ("2015", "Expense Clearing", "liability", "expense_clearing"),

    # --- Tax & payroll liabilities ---
    ("2100", "VAT Output Control", "liability", "vat_output_control"),
    ("2105", "Withholding Tax Control", "liability", "withholding_tax_control"),
    ("2110", "Payroll Payable Control", "liability", "payroll_payable_control"),
    ("2115", "Employee Reimbursement Liability", "liability", "employee_reimbursement_liability"),
    ("2120", "Corporate Card Clearing", "liability", "corporate_card_clearing"),
    ("2125", "Accrued Expense Provision", "liability", "accrued_expense_provision"),

    # --- Equity ---
    ("3000", "Share Capital", "equity", "share_capital"),
    ("3005", "Retained Earnings", "equity", "retained_earnings"),
    ("3010", "General Reserve", "equity", "general_reserve"),
    ("3015", "Statutory Reserve", "equity", "statutory_reserve"),

    # --- General service revenue ---
    ("4000", "Service Revenue", "income", "revenue"),
    ("4005", "Sales Revenue", "income", "sales_revenue"),
    ("4010", "Project Revenue Control", "income", "project_revenue_control"),

    # --- Forex / finance income ---
    ("4300", "Forex Gain", "income", "forex_gain"),
    ("4305", "Unrealized Forex Gain", "income", "unrealized_forex_gain"),

    # --- Direct costs ---
    ("5000", "Cost of Services", "expense", "cost_of_services"),
    ("5005", "Cost of Goods Sold", "expense", "cogs"),
    ("5010", "Project Cost Control", "expense", "project_cost_control"),
    ("5015", "Bad Debt Expense", "expense", "bad_debt_expense"),

    # --- Forex / finance expense ---
    ("5400", "Forex Loss", "expense", "forex_loss"),
    ("5405", "Unrealized Forex Loss", "expense", "unrealized_forex_loss"),

    # --- Operating expenses ---
    ("6000", "Operating Expenses", "expense", "operating_expenses"),
    ("6005", "Department Expense Control", "expense", "department_expense_control"),
    ("6010", "Depreciation Expense", "expense", "depreciation_expense"),
    ("6015", "Purchase Expense", "expense", "purchase_expense"),
    ("6020", "Disposal Gain/Loss", "income", "asset_disposal_gain_loss"),
    ("6025", "Production Variance Control", "expense", "production_variance_control"),
]


# ---------------------------------------------------------------------------
# Inventory management accounts
# Covers trading, manufacturing, and distribution businesses.
# IFRS references: IAS 2 (Inventories), IFRS 15 (Revenue)
# ---------------------------------------------------------------------------

INVENTORY_ACCOUNTS = [
    # --- Inventory assets (1300-1399) ---
    ("1300", "Raw Materials Inventory", "asset", "inventory_asset"),
    ("1305", "Work-In-Process Inventory", "asset", "manufacturing_wip"),
    ("1310", "Finished Goods Inventory", "asset", "work_in_progress_control"),
    ("1315", "Merchandise Inventory", "asset", "merchandise_inventory"),
    ("1320", "Inventory In Transit", "asset", "inventory_in_transit"),
    ("1325", "Consignment Inventory Control", "asset", "consignment_inventory_control"),
    ("1330", "Material Consumption Control", "asset", "material_consumption_control"),
    ("1335", "Inventory Provision", "liability", "inventory_provision"),

    # --- Inventory payables / clearing (2200-2299) ---
    ("2200", "Goods Received Not Invoiced (GRNI)", "liability", "inventory_grni"),
    ("2205", "Consignment Payable Control", "liability", "consignment_payable_control"),

    # --- Inventory revenue (4100-4199) ---
    ("4100", "Product Sales Revenue", "income", "product_sales_revenue"),
    ("4105", "Inventory Recovery Income", "income", "inventory_recovery_income"),

    # --- Inventory direct costs (5100-5199) ---
    ("5100", "Inventory Adjustment Expense", "expense", "inventory_adjustment"),
    ("5105", "Inventory Variance Expense", "expense", "inventory_variance"),
    ("5110", "Inventory Write-down Expense", "expense", "inventory_write_down_expense"),
    ("5115", "Freight and Handling Inward", "expense", "freight_inward"),
    ("5120", "Direct Labour Cost", "expense", "direct_labour"),
    ("5125", "Manufacturing Overhead Absorbed", "expense", "manufacturing_overhead"),
]


# ---------------------------------------------------------------------------
# Microfinance / SACCO / lending accounts
# Covers savings, loans, interest, penalties, provisioning.
# IFRS references: IFRS 9 (Financial Instruments), IAS 39, IFRS 7
# ---------------------------------------------------------------------------

MICROFINANCE_ACCOUNTS = [
    # --- Loan receivables by grade (1400-1499) ---
    ("1400", "Loan Receivables — Performing", "asset", "loan_receivables"),
    ("1405", "Loan Receivables — Watch", "asset", "loan_receivables_watch"),
    ("1410", "Loan Receivables — Substandard", "asset", "loan_receivables_substandard"),
    ("1415", "Loan Receivables — Doubtful", "asset", "loan_receivables_doubtful"),
    ("1420", "Loan Receivables — Loss", "asset", "loan_receivables_loss"),

    # --- Provisioning (contra-asset, 1450-1459) ---
    ("1450", "Loan Loss Provision — Stage 1 (12-month ECL)", "asset", "loan_loss_provision_stage1"),
    ("1455", "Loan Loss Provision — Stage 2 (Lifetime ECL)", "asset", "loan_loss_provision_stage2"),
    ("1460", "Loan Loss Provision — Stage 3 (Credit-Impaired)", "asset", "loan_loss_provision_stage3"),
    ("1465", "Interest Receivable — Loans", "asset", "loan_interest_receivable"),
    ("1470", "Penalty Receivable", "asset", "penalty_receivable"),

    # --- Member liabilities (2300-2399) ---
    ("2300", "Member Savings Deposits", "liability", "member_savings"),
    ("2305", "Fixed-Term Deposits", "liability", "fixed_term_deposits"),
    ("2310", "Dividend Payable to Members", "liability", "dividend_payable"),
    ("2315", "Loan Liability Control", "liability", "loan_liability_control"),
    ("2320", "Interest Payable Control", "liability", "interest_payable_control"),
    ("2325", "Loan Penalty Control", "liability", "loan_penalty_control"),
    ("2330", "Welfare Fund Liability", "liability", "welfare_fund_liability"),

    # --- Microfinance equity (3100-3199) ---
    ("3100", "Member Share Capital", "equity", "member_share_capital"),
    ("3105", "Statutory Liquidity Reserve (10%)", "equity", "statutory_liquidity_reserve"),
    ("3110", "Institutional Capital Reserve", "equity", "institutional_capital_reserve"),
    ("3115", "Loan Loss Reserve", "equity", "loan_loss_reserve"),

    # --- Interest & fee income (4200-4299) ---
    ("4200", "Interest Income on Loans", "income", "interest_income"),
    ("4205", "Fee Income — Loan Origination", "income", "loan_fee_income"),
    ("4210", "Penalty Income on Loans", "income", "penalty_income"),
    ("4215", "Interest Income on Investments", "income", "investment_interest_income"),
    ("4220", "Dividend Income", "income", "dividend_income"),

    # --- Loan expense (5200-5299) ---
    ("5200", "Interest Expense on Deposits", "expense", "deposit_interest_expense"),
    ("5205", "Loan Loss Provision Expense", "expense", "loan_loss_provision_expense"),
    ("5210", "Loan Write-off Expense", "expense", "loan_write_off_expense"),
    ("5215", "Loan Recovery Income", "income", "loan_recovery_income"),
]


# ---------------------------------------------------------------------------
# Real estate / property management accounts
# Covers rentals, lease receivables, investment property, deposits.
# IFRS references: IAS 40 (Investment Property), IFRS 16 (Leases), IAS 36
# ---------------------------------------------------------------------------

REAL_ESTATE_ACCOUNTS = [
    # --- Property assets (1600-1699) ---
    ("1600", "Investment Property — Land", "asset", "investment_property_land"),
    ("1605", "Investment Property — Buildings", "asset", "investment_property_buildings"),
    ("1610", "Accumulated Depreciation — Investment Property", "asset", "investment_property_accumulated_depreciation"),
    ("1615", "Owner-Occupied Property", "asset", "owner_occupied_property"),
    ("1620", "Right-of-Use Asset (IFRS 16)", "asset", "right_of_use_asset"),
    ("1625", "Accumulated Depreciation — ROU Asset", "asset", "rou_asset_accumulated_depreciation"),
    ("1630", "Rental Receivables", "asset", "rental_receivables"),
    ("1635", "Security Deposits Paid", "asset", "security_deposits_paid"),

    # --- Property liabilities (2600-2699) ---
    ("2600", "Deferred Rental Income", "liability", "deferred_rental_income"),
    ("2605", "Security Deposit Liability", "liability", "security_deposit_liability"),
    ("2610", "Lease Liability — Current (IFRS 16)", "liability", "lease_liability_current"),
    ("2615", "Lease Liability — Non-current (IFRS 16)", "liability", "lease_liability_non_current"),
    ("2620", "Property Maintenance Reserve", "liability", "property_maintenance_reserve"),
    ("2625", "Tenant Overpayment Liability", "liability", "tenant_overpayment_liability"),

    # --- Property equity (3200-3299) ---
    ("3200", "Property Revaluation Surplus (IAS 40)", "equity", "property_revaluation_surplus"),
    ("3205", "Capital Redemption Reserve", "equity", "capital_redemption_reserve"),

    # --- Rental & property income (4400-4499) ---
    ("4400", "Rental Income — Residential", "income", "rental_income_residential"),
    ("4405", "Rental Income — Commercial", "income", "rental_income_commercial"),
    ("4410", "Service Charge Income", "income", "service_charge_income"),
    ("4415", "Property Disposal Gain", "income", "property_disposal_gain"),
    ("4420", "Investment Property Fair Value Gain (IAS 40)", "income", "investment_property_fair_value_gain"),

    # --- Property expenses (5300-5399) ---
    ("5300", "Property Maintenance Expense", "expense", "property_maintenance"),
    ("5305", "Depreciation — Investment Property", "expense", "investment_property_depreciation"),
    ("5310", "Depreciation — ROU Asset (IFRS 16)", "expense", "rou_depreciation"),
    ("5315", "Lease Interest Expense (IFRS 16)", "expense", "lease_interest_expense"),
    ("5320", "Property Management Fees", "expense", "property_management_fees"),
    ("5325", "Ground Rent Expense", "expense", "ground_rent"),
    ("5330", "Property Disposal Loss", "expense", "property_disposal_loss"),
    ("5335", "Investment Property Fair Value Loss (IAS 40)", "expense", "investment_property_fair_value_loss"),

    # --- Aggregated rental income alias (backward-compat) ---
    ("4399", "Rental Income — Combined", "income", "rental_income"),
]


# ---------------------------------------------------------------------------
# Registry: maps business type → additional account lists to include
# ---------------------------------------------------------------------------

BUSINESS_TYPE_ACCOUNTS: dict[str, list] = {
    "general": [],
    "inventory": INVENTORY_ACCOUNTS,
    "microfinance": MICROFINANCE_ACCOUNTS,
    "real_estate": REAL_ESTATE_ACCOUNTS,
    "all": INVENTORY_ACCOUNTS + MICROFINANCE_ACCOUNTS + REAL_ESTATE_ACCOUNTS,
}


# ---------------------------------------------------------------------------
# Control account categories
# A SubLedgerAccount is required for every posting to these accounts.
# ---------------------------------------------------------------------------

CONTROL_ACCOUNT_CATEGORIES = {
    # Receivables / payables
    "accounts_receivable",
    "accounts_payable",
    "loan_receivables",
    "rental_receivables",
    # Cash controls
    "cash_and_cash_equivalent_control",
    "electronic_money_control",
    # Staff / payroll
    "staff_receivable_control",
    "payroll_payable_control",
    # Inventory controls
    "inventory_asset",
    "manufacturing_wip",
    "work_in_progress_control",
    "material_consumption_control",
    "production_variance_control",
    "consignment_inventory_control",
    "consignment_payable_control",
    # Fixed assets
    "fixed_assets",
    "accumulated_depreciation",
    # Microfinance
    "member_savings",
    "loan_liability_control",
    "interest_payable_control",
    "loan_penalty_control",
    # Finance controls
    "intercompany_control_account",
    "vat_input_control",
    "vat_output_control",
    "withholding_tax_control",
    # Revenue / cost controls
    "project_revenue_control",
    "project_cost_control",
}


# Accounts that REQUIRE a SubLedgerAccount reference on every GL posting.
# Inventory / manufacturing accounts use a separate InventoryJournalEntry
# system and can be posted to directly at the GL level.
RESTRICTED_CONTROL_ACCOUNT_CATEGORIES = {
    "accounts_receivable",
    "accounts_payable",
    "member_savings",
    "loan_receivables",
    "interest_receivable",
    "loan_interest_receivable",
    "staff_receivable_control",
    "payroll_payable_control",
    "loan_liability_control",
    "interest_payable_control",
    "loan_penalty_control",
    "consignment_payable_control",
    "rental_receivables",
}


# ---------------------------------------------------------------------------
# Categories whose accounts are aggregation/reporting parents only.
# Direct journal postings to these accounts are blocked (allows_manual_posting=False).
# Individual payment-method accounts created via create_payment_method() sit
# beneath these parents and are the actual posting targets.
# ---------------------------------------------------------------------------

AGGREGATION_ONLY_CATEGORIES = {
    "cash_and_cash_equivalent_control",
    "electronic_money_control",
}


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _seed_accounts(accounts, branch, base_currency, account_map):
    for code, name, account_type, category in accounts:
        is_control = category in CONTROL_ACCOUNT_CATEGORIES
        is_restricted = category in RESTRICTED_CONTROL_ACCOUNT_CATEGORIES
        is_aggregation_only = category in AGGREGATION_ONLY_CATEGORIES
        account, _ = Account.objects.get_or_create(
            code=code,
            branch=branch,
            defaults={
                "name": name,
                "account_type": account_type,
                "category": category,
                "currency": base_currency,
                # Aggregation-only and restricted accounts both block direct posting.
                "allows_manual_posting": not is_restricted and not is_aggregation_only,
                "is_control_account": is_control,
            },
        )
        account_map[category] = account.code


def seed_default_chart_of_accounts(
    *,
    branch=None,
    currency: str = DEFAULT_CURRENCY,
    business_type: str = "general",
) -> "AccountingConfiguration":
    """
    Seed the chart of accounts for *branch* (or global if None).

    ``business_type`` controls which domain-specific account groups are added
    on top of the always-present CORE_ACCOUNTS:

    - ``general``      – core accounts only (services, trading basics)
    - ``inventory``    – core + inventory / manufacturing / distribution
    - ``microfinance`` – core + SACCO / lending / savings accounts
    - ``real_estate``  – core + property / lease / rental accounts
    - ``all``          – core + all domain accounts
    """
    if business_type not in BUSINESS_TYPE_ACCOUNTS:
        raise ValueError(
            f"Unknown business_type '{business_type}'. "
            f"Choose from: {', '.join(BUSINESS_TYPE_ACCOUNTS)}"
        )

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

    account_map: dict[str, str] = {}

    _seed_accounts(CORE_ACCOUNTS, branch, base_currency, account_map)

    domain_accounts = BUSINESS_TYPE_ACCOUNTS[business_type]
    if domain_accounts:
        _seed_accounts(domain_accounts, branch, base_currency, account_map)

    config.default_accounts = {**config.default_accounts, **account_map}
    config.save(update_fields=["default_accounts", "updated_at"])
    return config


def seed_default_payment_methods(*, branch_id) -> None:
    """
    Create the standard set of payment methods for a branch.

    Called by create_branch() after seed_default_chart_of_accounts().
    Each method atomically creates its own GL account in the reserved range.
    Safe to call multiple times — skips any method whose code already exists.
    """
    from apps.financials.services.payment_method_service import create_payment_method
    from apps.financials.models import PaymentMethod

    defaults = [
        ("Cash", "cash", "cash"),
        ("MTN Mobile Money", "mtn_mobile_money", "mobile_money"),
        ("Airtel Mobile Money", "airtel_mobile_money", "mobile_money"),
        ("Card / POS", "card", "card"),
    ]

    for name, code, account_type in defaults:
        if PaymentMethod.objects.filter(branch_id=branch_id, code=code).exists():
            continue
        try:
            create_payment_method(
                branch_id=branch_id,
                name=name,
                code=code,
                account_type=account_type,
            )
        except Exception:
            pass
