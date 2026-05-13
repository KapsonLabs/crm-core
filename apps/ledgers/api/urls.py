from django.urls import path

from apps.ledgers.api.viewsets import (
    AccountDetailView,
    AccountListCreateView,
    ControlAccountDetailView,
    ControlAccountListView,
    CurrencyDetailView,
    CurrencyListView,
    ExchangeRateDetailView,
    ExchangeRateListView,
    FiscalPeriodDetailView,
    FiscalPeriodListCreateView,
    InventoryAccrualDetailView,
    InventoryAccrualListView,
    InventoryJournalEntryDetailView,
    InventoryJournalEntryListView,
    InventoryLedgerEntryDetailView,
    InventoryLedgerEntryListView,
    InventoryValuationLayerDetailView,
    InventoryValuationLayerListView,
    InventoryWriteDownDetailView,
    InventoryWriteDownListView,
    JournalEntryDetailView,
    JournalEntryListView,
    JournalEntryPostView,
    JournalEntryReverseView,
    LandedCostAllocationDetailView,
    LandedCostAllocationListView,
    LedgerEntryDetailView,
    LedgerEntryListView,
    ManufacturingCostAllocationDetailView,
    ManufacturingCostAllocationListView,
    SubLedgerAccountDetailView,
    SubLedgerAccountListView,
    SubLedgerEntryDetailView,
    SubLedgerEntryListView,
)

urlpatterns = [
    # Accounts
    path("accounts/", AccountListCreateView.as_view(), name="ledger-account-list"),
    path("accounts/<uuid:pk>/", AccountDetailView.as_view(), name="ledger-account-detail"),

    # Control Accounts
    path("control-accounts/", ControlAccountListView.as_view(), name="control-account-list"),
    path("control-accounts/<uuid:pk>/", ControlAccountDetailView.as_view(), name="control-account-detail"),

    # SubLedger Accounts
    path("subledgers/", SubLedgerAccountListView.as_view(), name="subledger-account-list"),
    path("subledgers/<uuid:pk>/", SubLedgerAccountDetailView.as_view(), name="subledger-account-detail"),

    # SubLedger Entries
    path("subledger-entries/", SubLedgerEntryListView.as_view(), name="subledger-entry-list"),
    path("subledger-entries/<uuid:pk>/", SubLedgerEntryDetailView.as_view(), name="subledger-entry-detail"),

    # Currencies
    path("currencies/", CurrencyListView.as_view(), name="ledger-currency-list"),
    path("currencies/<uuid:pk>/", CurrencyDetailView.as_view(), name="ledger-currency-detail"),

    # Exchange Rates
    path("exchange-rates/", ExchangeRateListView.as_view(), name="ledger-exchange-rate-list"),
    path("exchange-rates/<uuid:pk>/", ExchangeRateDetailView.as_view(), name="ledger-exchange-rate-detail"),

    # Fiscal Periods
    path("periods/", FiscalPeriodListCreateView.as_view(), name="ledger-period-list"),
    path("periods/<uuid:pk>/", FiscalPeriodDetailView.as_view(), name="ledger-period-detail"),

    # Journal Entries
    path("journals/", JournalEntryListView.as_view(), name="ledger-journal-list"),
    path("journals/<uuid:pk>/", JournalEntryDetailView.as_view(), name="ledger-journal-detail"),
    path("journals/<uuid:pk>/post/", JournalEntryPostView.as_view(), name="ledger-journal-post"),
    path("journals/<uuid:pk>/reverse/", JournalEntryReverseView.as_view(), name="ledger-journal-reverse"),

    # Ledger Entries
    path("ledger-entries/", LedgerEntryListView.as_view(), name="ledger-entry-list"),
    path("ledger-entries/<uuid:pk>/", LedgerEntryDetailView.as_view(), name="ledger-entry-detail"),

    # Inventory — Valuation Layers
    path("inventory-valuation-layers/", InventoryValuationLayerListView.as_view(), name="inventory-valuation-layer-list"),
    path("inventory-valuation-layers/<uuid:pk>/", InventoryValuationLayerDetailView.as_view(), name="inventory-valuation-layer-detail"),

    # Inventory — Journal Entries
    path("inventory-journals/", InventoryJournalEntryListView.as_view(), name="inventory-journal-list"),
    path("inventory-journals/<uuid:pk>/", InventoryJournalEntryDetailView.as_view(), name="inventory-journal-detail"),

    # Inventory — Ledger Entries
    path("inventory-ledger/", InventoryLedgerEntryListView.as_view(), name="inventory-ledger-list"),
    path("inventory-ledger/<uuid:pk>/", InventoryLedgerEntryDetailView.as_view(), name="inventory-ledger-detail"),

    # Inventory — Landed Cost Allocations
    path("landed-cost-allocations/", LandedCostAllocationListView.as_view(), name="landed-cost-allocation-list"),
    path("landed-cost-allocations/<uuid:pk>/", LandedCostAllocationDetailView.as_view(), name="landed-cost-allocation-detail"),

    # Inventory — Write-downs
    path("inventory-write-downs/", InventoryWriteDownListView.as_view(), name="inventory-write-down-list"),
    path("inventory-write-downs/<uuid:pk>/", InventoryWriteDownDetailView.as_view(), name="inventory-write-down-detail"),

    # Inventory — Manufacturing Cost Allocations
    path("manufacturing-cost-allocations/", ManufacturingCostAllocationListView.as_view(), name="manufacturing-cost-allocation-list"),
    path("manufacturing-cost-allocations/<uuid:pk>/", ManufacturingCostAllocationDetailView.as_view(), name="manufacturing-cost-allocation-detail"),

    # Inventory — Accruals
    path("inventory-accruals/", InventoryAccrualListView.as_view(), name="inventory-accrual-list"),
    path("inventory-accruals/<uuid:pk>/", InventoryAccrualDetailView.as_view(), name="inventory-accrual-detail"),
]
