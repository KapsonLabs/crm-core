from __future__ import annotations

from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

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


def _ok(data, http_status=status.HTTP_200_OK):
    return Response({"status": http_status, "data": data}, status=http_status)


def _bad(message, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({"status": http_status, "message": message}, status=http_status)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

class AccountListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAccountingManager()]
        return [IsAccountingViewer()]

    def get(self, request):
        qs = Account.objects.all().order_by("code")
        branch_id = request.query_params.get("branch_id")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return _ok(AccountSerializer(qs, many=True).data)

    def post(self, request):
        ser = AccountSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        account = ser.save()
        return _ok(AccountSerializer(account).data, status.HTTP_201_CREATED)


class AccountDetailView(APIView):
    def get_permissions(self):
        if self.request.method in {"PATCH", "DELETE"}:
            return [IsAccountingManager()]
        return [IsAccountingViewer()]

    def get(self, request, pk):
        account = get_object_or_404(Account, pk=pk)
        return _ok(AccountSerializer(account).data)

    def patch(self, request, pk):
        account = get_object_or_404(Account, pk=pk)
        ser = AccountSerializer(account, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        account = ser.save()
        return _ok(AccountSerializer(account).data)

    def delete(self, request, pk):
        account = get_object_or_404(Account, pk=pk)
        account.delete()
        return Response({"status": 204, "data": None}, status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Control Accounts
# ---------------------------------------------------------------------------

class ControlAccountListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = ControlAccount.objects.select_related("gl_account", "currency").order_by("code")
        return _ok(ControlAccountSerializer(qs, many=True).data)


class ControlAccountDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            ControlAccount.objects.select_related("gl_account", "currency"), pk=pk
        )
        return _ok(ControlAccountSerializer(obj).data)


# ---------------------------------------------------------------------------
# SubLedger Accounts
# ---------------------------------------------------------------------------

class SubLedgerAccountListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = SubLedgerAccount.objects.select_related(
            "parent_control_account", "currency", "gl_account"
        ).order_by("account_code")
        entity_type = request.query_params.get("entity_type")
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        entity_id = request.query_params.get("entity_id")
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        return _ok(SubLedgerAccountSerializer(qs, many=True).data)


class SubLedgerAccountDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            SubLedgerAccount.objects.select_related(
                "parent_control_account", "currency", "gl_account"
            ),
            pk=pk,
        )
        return _ok(SubLedgerAccountSerializer(obj).data)


# ---------------------------------------------------------------------------
# SubLedger Entries
# ---------------------------------------------------------------------------

class SubLedgerEntryListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = SubLedgerEntry.objects.select_related("subledger_account").order_by(
            "date", "created_at", "id"
        )
        subledger_id = request.query_params.get("subledger_account_id")
        if subledger_id:
            qs = qs.filter(subledger_account_id=subledger_id)
        return _ok(SubLedgerEntrySerializer(qs, many=True).data)


class SubLedgerEntryDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            SubLedgerEntry.objects.select_related("subledger_account"), pk=pk
        )
        return _ok(SubLedgerEntrySerializer(obj).data)


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------

class CurrencyListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = Currency.objects.all().order_by("code")
        return _ok(CurrencySerializer(qs, many=True).data)


class CurrencyDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(Currency, pk=pk)
        return _ok(CurrencySerializer(obj).data)


# ---------------------------------------------------------------------------
# Exchange Rates
# ---------------------------------------------------------------------------

class ExchangeRateListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = ExchangeRate.objects.select_related("from_currency", "to_currency").all()
        from_code = request.query_params.get("from_currency")
        if from_code:
            qs = qs.filter(from_currency__code=from_code)
        to_code = request.query_params.get("to_currency")
        if to_code:
            qs = qs.filter(to_currency__code=to_code)
        return _ok(ExchangeRateSerializer(qs, many=True).data)


class ExchangeRateDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            ExchangeRate.objects.select_related("from_currency", "to_currency"), pk=pk
        )
        return _ok(ExchangeRateSerializer(obj).data)


# ---------------------------------------------------------------------------
# Fiscal Periods
# ---------------------------------------------------------------------------

class FiscalPeriodListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAccountingManager()]
        return [IsAccountingViewer()]

    def get(self, request):
        qs = FiscalPeriod.objects.all().order_by("-start_date")
        branch_id = request.query_params.get("branch_id")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return _ok(FiscalPeriodSerializer(qs, many=True).data)

    def post(self, request):
        ser = FiscalPeriodSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        period = ser.save()
        return _ok(FiscalPeriodSerializer(period).data, status.HTTP_201_CREATED)


class FiscalPeriodDetailView(APIView):
    def get_permissions(self):
        if self.request.method in {"PATCH", "DELETE"}:
            return [IsAccountingManager()]
        return [IsAccountingViewer()]

    def get(self, request, pk):
        obj = get_object_or_404(FiscalPeriod, pk=pk)
        return _ok(FiscalPeriodSerializer(obj).data)

    def patch(self, request, pk):
        obj = get_object_or_404(FiscalPeriod, pk=pk)
        ser = FiscalPeriodSerializer(obj, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        period = ser.save()
        return _ok(FiscalPeriodSerializer(period).data)

    def delete(self, request, pk):
        obj = get_object_or_404(FiscalPeriod, pk=pk)
        obj.delete()
        return Response({"status": 204, "data": None}, status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Journal Entries
# ---------------------------------------------------------------------------

class JournalEntryListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = JournalEntry.objects.prefetch_related("lines", "lines__account").all()
        source_module = request.query_params.get("source_module")
        if source_module:
            qs = qs.filter(source_module=source_module)
        journal_status = request.query_params.get("status")
        if journal_status:
            qs = qs.filter(status=journal_status)
        branch_id = request.query_params.get("branch_id")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return _ok(JournalEntrySerializer(qs, many=True).data)


class JournalEntryDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            JournalEntry.objects.prefetch_related("lines", "lines__account"), pk=pk
        )
        return _ok(JournalEntrySerializer(obj).data)


class JournalEntryPostView(APIView):
    permission_classes = [IsAccountingManager]

    def post(self, request, pk):
        journal = post_journal_entry(
            journal_entry_id=pk,
            performed_by_id=getattr(request.user, "id", None),
        )
        return _ok(JournalEntrySerializer(journal).data)


class JournalEntryReverseView(APIView):
    permission_classes = [IsAccountingManager]

    def post(self, request, pk):
        reversal_date_raw = request.data.get("reversal_date")
        if not reversal_date_raw:
            return _bad("reversal_date is required.")
        try:
            reversal_date = date.fromisoformat(reversal_date_raw)
        except ValueError:
            return _bad("reversal_date must be a valid ISO date (YYYY-MM-DD).")
        reversal = reverse_journal_entry(
            journal_entry_id=pk,
            reversal_date=reversal_date,
            created_by_id=getattr(request.user, "id", None),
            reason=request.data.get("reason", ""),
        )
        return _ok(JournalEntrySerializer(reversal).data, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Ledger Entries
# ---------------------------------------------------------------------------

class LedgerEntryListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = LedgerEntry.objects.select_related(
            "account", "journal_line", "journal_line__journal_entry"
        ).all()
        account_id = request.query_params.get("account_id")
        if account_id:
            qs = qs.filter(account_id=account_id)
        branch_id = request.query_params.get("branch_id")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return _ok(LedgerEntrySerializer(qs, many=True).data)


class LedgerEntryDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            LedgerEntry.objects.select_related(
                "account", "journal_line", "journal_line__journal_entry"
            ),
            pk=pk,
        )
        return _ok(LedgerEntrySerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Valuation Layers
# ---------------------------------------------------------------------------

class InventoryValuationLayerListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = InventoryValuationLayer.objects.select_related("currency").all()
        return _ok(InventoryValuationLayerSerializer(qs, many=True).data)


class InventoryValuationLayerDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(InventoryValuationLayer.objects.select_related("currency"), pk=pk)
        return _ok(InventoryValuationLayerSerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Journal Entries
# ---------------------------------------------------------------------------

class InventoryJournalEntryListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = InventoryJournalEntry.objects.prefetch_related(
            "lines", "lines__account", "lines__currency"
        ).all()
        return _ok(InventoryJournalEntrySerializer(qs, many=True).data)


class InventoryJournalEntryDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(
            InventoryJournalEntry.objects.prefetch_related(
                "lines", "lines__account", "lines__currency"
            ),
            pk=pk,
        )
        return _ok(InventoryJournalEntrySerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Ledger Entries
# ---------------------------------------------------------------------------

class InventoryLedgerEntryListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = InventoryLedgerEntry.objects.all()
        return _ok(InventoryLedgerEntrySerializer(qs, many=True).data)


class InventoryLedgerEntryDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(InventoryLedgerEntry, pk=pk)
        return _ok(InventoryLedgerEntrySerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Landed Cost Allocations
# ---------------------------------------------------------------------------

class LandedCostAllocationListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = LandedCostAllocation.objects.select_related("currency").all()
        return _ok(LandedCostAllocationSerializer(qs, many=True).data)


class LandedCostAllocationDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(LandedCostAllocation.objects.select_related("currency"), pk=pk)
        return _ok(LandedCostAllocationSerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Write-downs
# ---------------------------------------------------------------------------

class InventoryWriteDownListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = InventoryWriteDown.objects.all()
        return _ok(InventoryWriteDownSerializer(qs, many=True).data)


class InventoryWriteDownDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(InventoryWriteDown, pk=pk)
        return _ok(InventoryWriteDownSerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Manufacturing Cost Allocations
# ---------------------------------------------------------------------------

class ManufacturingCostAllocationListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = ManufacturingCostAllocation.objects.all()
        return _ok(ManufacturingCostAllocationSerializer(qs, many=True).data)


class ManufacturingCostAllocationDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(ManufacturingCostAllocation, pk=pk)
        return _ok(ManufacturingCostAllocationSerializer(obj).data)


# ---------------------------------------------------------------------------
# Inventory — Accruals
# ---------------------------------------------------------------------------

class InventoryAccrualListView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        qs = InventoryAccrual.objects.all()
        return _ok(InventoryAccrualSerializer(qs, many=True).data)


class InventoryAccrualDetailView(APIView):
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        obj = get_object_or_404(InventoryAccrual, pk=pk)
        return _ok(InventoryAccrualSerializer(obj).data)
