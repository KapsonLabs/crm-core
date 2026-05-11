from rest_framework.routers import DefaultRouter

from apps.ledgers.api.viewsets import (
    AccountViewSet,
    ControlAccountViewSet,
    CurrencyViewSet,
    ExchangeRateViewSet,
    FiscalPeriodViewSet,
    InventoryAccrualViewSet,
    InventoryJournalEntryViewSet,
    InventoryLedgerEntryViewSet,
    InventoryValuationLayerViewSet,
    InventoryWriteDownViewSet,
    JournalEntryViewSet,
    LandedCostAllocationViewSet,
    LedgerEntryViewSet,
    ManufacturingCostAllocationViewSet,
    SubLedgerAccountViewSet,
    SubLedgerEntryViewSet,
)

router = DefaultRouter()
router.register("accounts", AccountViewSet, basename="ledger-account")
router.register("control-accounts", ControlAccountViewSet, basename="control-account")
router.register("subledgers", SubLedgerAccountViewSet, basename="subledger-account")
router.register("subledger-entries", SubLedgerEntryViewSet, basename="subledger-entry")
router.register("currencies", CurrencyViewSet, basename="ledger-currency")
router.register("exchange-rates", ExchangeRateViewSet, basename="ledger-exchange-rate")
router.register("periods", FiscalPeriodViewSet, basename="ledger-period")
router.register("journals", JournalEntryViewSet, basename="ledger-journal")
router.register("ledger-entries", LedgerEntryViewSet, basename="ledger-entry")
router.register("inventory-valuation-layers", InventoryValuationLayerViewSet, basename="inventory-valuation-layer")
router.register("inventory-journals", InventoryJournalEntryViewSet, basename="inventory-journal")
router.register("inventory-ledger", InventoryLedgerEntryViewSet, basename="inventory-ledger")
router.register("landed-cost-allocations", LandedCostAllocationViewSet, basename="landed-cost-allocation")
router.register("inventory-write-downs", InventoryWriteDownViewSet, basename="inventory-write-down")
router.register("manufacturing-cost-allocations", ManufacturingCostAllocationViewSet, basename="manufacturing-cost-allocation")
router.register("inventory-accruals", InventoryAccrualViewSet, basename="inventory-accrual")

urlpatterns = router.urls
