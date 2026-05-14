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
from apps.ledgers.services.coa_service import get_account_drill_down, get_chart_with_balances
from apps.ledgers.services.journal_service import post_journal_entry, reverse_journal_entry
from apps.ledgers.utils.ledger import generate_general_ledger


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


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------

class ChartOfAccountsView(APIView):
    """
    Full chart of accounts with aggregated balances.

    Query params:
      branch_id            — UUID, defaults to the authenticated user's branch
      as_of_date           — YYYY-MM-DD, cumulative balance up to this date
      start_date           — YYYY-MM-DD, period start (P&L mode)
      end_date             — YYYY-MM-DD, period end (P&L mode)
      account_type         — filter: asset | liability | equity | income | expense
      with_zero_balances   — true (default) | false

    Balance modes:
      as_of_date only      → cumulative (B/S view)
      start_date + end_date → period-scoped (P&L view)
      all three            → mixed: cumulative for B/S types, period for P&L types
      none                 → cumulative as of today
    """
    permission_classes = [IsAccountingViewer]

    def get(self, request):
        from datetime import date as date_type

        branch_id = request.query_params.get("branch_id") or getattr(request.user, "branch_id", None)

        def _parse_date(key):
            val = request.query_params.get(key)
            if val:
                try:
                    return date_type.fromisoformat(val)
                except ValueError:
                    return None
            return None

        as_of_date = _parse_date("as_of_date")
        start_date = _parse_date("start_date")
        end_date = _parse_date("end_date")
        account_type = request.query_params.get("account_type") or None
        include_zeros = request.query_params.get("with_zero_balances", "true").lower() != "false"

        data = get_chart_with_balances(
            branch=branch_id,
            as_of_date=as_of_date,
            start_date=start_date,
            end_date=end_date,
            account_type=account_type,
            include_zero_balances=include_zeros,
        )

        return _ok({
            "branch_id": str(branch_id) if branch_id else None,
            "as_of_date": str(as_of_date or date_type.today()),
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "count": len(data),
            "accounts": data,
        })


class AccountDrillDownView(APIView):
    """
    Single account node + its direct children, each with aggregated balance.

    Accepts the same date query params as ChartOfAccountsView.
    Use this to navigate the tree: click a parent → see its breakdown.
    Children with their own children will have children_count > 0 —
    drill into them with another request to this endpoint.
    """
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        from datetime import date as date_type

        branch_id = request.query_params.get("branch_id") or getattr(request.user, "branch_id", None)

        def _parse_date(key):
            val = request.query_params.get(key)
            if val:
                try:
                    return date_type.fromisoformat(val)
                except ValueError:
                    return None
            return None

        result = get_account_drill_down(
            account_id=pk,
            branch=branch_id,
            as_of_date=_parse_date("as_of_date"),
            start_date=_parse_date("start_date"),
            end_date=_parse_date("end_date"),
        )
        if not result:
            return _bad("Account not found.", status.HTTP_404_NOT_FOUND)
        return _ok(result)


class AccountLedgerLinesView(APIView):
    """
    Journal lines (ledger entries) for a single account.

    Query params:
      branch_id   — UUID
      start_date  — YYYY-MM-DD
      end_date    — YYYY-MM-DD
    """
    permission_classes = [IsAccountingViewer]

    def get(self, request, pk):
        from datetime import date as date_type

        account = get_object_or_404(Account, pk=pk)
        branch_id = request.query_params.get("branch_id") or getattr(request.user, "branch_id", None)

        def _parse_date(key):
            val = request.query_params.get(key)
            if val:
                try:
                    return date_type.fromisoformat(val)
                except ValueError:
                    return None
            return None

        entries = generate_general_ledger(
            account_id=account.id,
            branch=branch_id,
            start_date=_parse_date("start_date"),
            end_date=_parse_date("end_date"),
        )

        # Prefetch related for serializer efficiency
        entry_qs = LedgerEntry.objects.filter(
            pk__in=[e.id for e in entries]
        ).select_related("account", "currency", "journal_line", "journal_line__journal_entry").order_by("date", "created_at")

        return _ok({
            "account": {
                "id": str(account.id),
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
            },
            "count": entry_qs.count(),
            "lines": LedgerEntrySerializer(entry_qs, many=True).data,
        })
