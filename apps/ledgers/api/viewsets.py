from __future__ import annotations

from datetime import date

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.ledgers.api.permissions import IsAccountingManager, IsAccountingViewer
from apps.ledgers.api.serializers import (
    AccountSerializer,
    ControlAccountSerializer,
    CurrencySerializer,
    ExchangeRateSerializer,
    FiscalPeriodSerializer,
    InventoryAccrualSerializer,
    InventoryJournalEntrySerializer,
    InventoryLedgerEntrySerializer,
    InventoryValuationLayerSerializer,
    InventoryWriteDownSerializer,
    LandedCostAllocationSerializer,
    ManufacturingCostAllocationSerializer,
    JournalEntrySerializer,
    LedgerEntrySerializer,
    SubLedgerAccountSerializer,
    SubLedgerEntrySerializer,
)
from apps.ledgers.models import (
    Account,
    ControlAccount,
    Currency,
    ExchangeRate,
    FiscalPeriod,
    InventoryAccrual,
    InventoryJournalEntry,
    InventoryLedgerEntry,
    InventoryValuationLayer,
    InventoryWriteDown,
    JournalEntry,
    LandedCostAllocation,
    LedgerEntry,
    ManufacturingCostAllocation,
    SubLedgerAccount,
    SubLedgerEntry,
)
from apps.ledgers.services.journal_service import post_journal_entry, reverse_journal_entry


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by("code")
    serializer_class = AccountSerializer
    permission_classes = [IsAccountingManager]


class ControlAccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ControlAccount.objects.select_related("gl_account", "currency").all().order_by("code")
    serializer_class = ControlAccountSerializer
    permission_classes = [IsAccountingViewer]


class SubLedgerAccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = SubLedgerAccount.objects.select_related("parent_control_account", "currency", "gl_account").all().order_by("account_code")
    serializer_class = SubLedgerAccountSerializer
    permission_classes = [IsAccountingViewer]


class SubLedgerEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = SubLedgerEntry.objects.select_related("subledger_account").all().order_by("date", "created_at", "id")
    serializer_class = SubLedgerEntrySerializer
    permission_classes = [IsAccountingViewer]


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Currency.objects.all().order_by("code")
    serializer_class = CurrencySerializer
    permission_classes = [IsAccountingViewer]


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExchangeRate.objects.select_related("from_currency", "to_currency").all()
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAccountingViewer]


class FiscalPeriodViewSet(viewsets.ModelViewSet):
    queryset = FiscalPeriod.objects.all().order_by("-start_date")
    serializer_class = FiscalPeriodSerializer
    permission_classes = [IsAccountingManager]


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.prefetch_related("lines", "lines__account").all()
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAccountingViewer]

    @action(detail=True, methods=["post"], permission_classes=[IsAccountingManager])
    def post(self, request, pk=None):
        journal = post_journal_entry(
            journal_entry_id=pk,
            performed_by_id=getattr(request.user, "id", None),
        )
        return Response(JournalEntrySerializer(journal).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAccountingManager])
    def reverse(self, request, pk=None):
        reversal = reverse_journal_entry(
            journal_entry_id=pk,
            reversal_date=date.fromisoformat(request.data["reversal_date"]),
            created_by_id=getattr(request.user, "id", None),
            reason=request.data.get("reason", ""),
        )
        return Response(JournalEntrySerializer(reversal).data, status=status.HTTP_201_CREATED)


class LedgerEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = LedgerEntry.objects.select_related("account", "journal_line", "journal_line__journal_entry").all()
    serializer_class = LedgerEntrySerializer
    permission_classes = [IsAccountingViewer]


class InventoryValuationLayerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = InventoryValuationLayer.objects.select_related("currency").all()
    serializer_class = InventoryValuationLayerSerializer
    permission_classes = [IsAccountingViewer]


class InventoryJournalEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = InventoryJournalEntry.objects.prefetch_related("lines", "lines__account", "lines__currency").all()
    serializer_class = InventoryJournalEntrySerializer
    permission_classes = [IsAccountingViewer]


class InventoryLedgerEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = InventoryLedgerEntry.objects.all()
    serializer_class = InventoryLedgerEntrySerializer
    permission_classes = [IsAccountingViewer]


class LandedCostAllocationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = LandedCostAllocation.objects.select_related("currency").all()
    serializer_class = LandedCostAllocationSerializer
    permission_classes = [IsAccountingViewer]


class InventoryWriteDownViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = InventoryWriteDown.objects.all()
    serializer_class = InventoryWriteDownSerializer
    permission_classes = [IsAccountingViewer]


class ManufacturingCostAllocationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ManufacturingCostAllocation.objects.all()
    serializer_class = ManufacturingCostAllocationSerializer
    permission_classes = [IsAccountingViewer]


class InventoryAccrualViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = InventoryAccrual.objects.all()
    serializer_class = InventoryAccrualSerializer
    permission_classes = [IsAccountingViewer]
