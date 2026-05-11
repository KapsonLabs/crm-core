from __future__ import annotations
from datetime import date
from uuid import UUID

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.ledgers.api.permissions import IsAccountingManager, IsAccountingViewer

from apps.expense_accounting.api.serializers.expense_serializers import (
    ApproveExpenseSerializer,
    CreateExpenseSerializer,
    CorporateCardTransactionSerializer,
    ExpenseBudgetSerializer,
    ExpenseCategorySerializer,
    ExpenseTransactionSerializer,
    PayExpenseSerializer,
    PostExpenseSerializer,
    PrepaidExpenseScheduleSerializer,
    ReverseExpenseSerializer,
)
from apps.expense_accounting.models import (
    CorporateCardTransaction,
    ExpenseBudget,
    ExpenseCategory,
    ExpenseTransaction,
    PrepaidExpenseSchedule,
)
from apps.expense_accounting.reports.expense_reports import (
    generate_budget_variance_report,
    generate_department_expense_report,
    generate_employee_claims_report,
    generate_expense_aging_report,
    generate_expense_analysis,
    generate_expense_trend_report,
    generate_prepaid_expense_report,
    generate_project_expense_report,
    generate_tax_deduction_report,
)
from apps.expense_accounting.services.expense_posting_service import (
    create_expense,
    pay_expense,
    post_expense,
    reverse_expense,
    submit_expense,
)
from apps.expense_accounting.services.expense_approval_service import (
    approve_expense,
    reject_expense,
)


class ExpenseCategoryViewSet(ModelViewSet):
    queryset = ExpenseCategory.objects.filter(is_active=True)
    serializer_class = ExpenseCategorySerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAccountingViewer()]
        return [IsAccountingManager()]


class ExpenseTransactionViewSet(ModelViewSet):
    serializer_class = ExpenseTransactionSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAccountingViewer()]
        return [IsAccountingManager()]

    def get_queryset(self):
        qs = ExpenseTransaction.objects.select_related(
            "expense_category", "currency", "journal_entry"
        ).prefetch_related("lines", "approvals")
        branch = self.request.query_params.get("branch")
        status_filter = self.request.query_params.get("status")
        department = self.request.query_params.get("department")
        project = self.request.query_params.get("project")
        if branch:
            qs = qs.filter(branch=branch)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if department:
            qs = qs.filter(department=department)
        if project:
            qs = qs.filter(project=project)
        return qs

    def create(self, request, *args, **kwargs):
        ser = CreateExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        expense = create_expense(
            **d,
            created_by_id=request.user.id,
        )
        return Response(ExpenseTransactionSerializer(expense).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        expense = self.get_object()
        result = submit_expense(expense_id=expense.id, submitted_by_id=request.user.id)
        return Response(ExpenseTransactionSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        ser = ApproveExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = approve_expense(
            expense_id=self.get_object().id,
            approver_id=request.user.id,
            remarks=ser.validated_data.get("remarks", ""),
        )
        return Response(ExpenseTransactionSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        ser = ApproveExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = reject_expense(
            expense_id=self.get_object().id,
            approver_id=request.user.id,
            remarks=ser.validated_data.get("remarks", ""),
        )
        return Response(ExpenseTransactionSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="post")
    def post_to_ledger(self, request, pk=None):
        ser = PostExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = post_expense(
            expense_id=self.get_object().id,
            posted_by_id=request.user.id,
            **ser.validated_data,
        )
        return Response(ExpenseTransactionSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        ser = PayExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = pay_expense(
            expense_id=self.get_object().id,
            paid_by_id=request.user.id,
            **ser.validated_data,
        )
        return Response(result)

    @action(detail=True, methods=["post"], url_path="reverse")
    def reverse(self, request, pk=None):
        ser = ReverseExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = reverse_expense(
            expense_id=self.get_object().id,
            reversed_by_id=request.user.id,
            **ser.validated_data,
        )
        return Response(ExpenseTransactionSerializer(result).data)


class PrepaidExpenseScheduleViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAccountingViewer]
    serializer_class = PrepaidExpenseScheduleSerializer

    def get_queryset(self):
        return PrepaidExpenseSchedule.objects.select_related(
            "expense_transaction__expense_category",
        ).filter(status=PrepaidExpenseSchedule.Status.ACTIVE)


class ExpenseBudgetViewSet(ModelViewSet):
    serializer_class = ExpenseBudgetSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAccountingViewer()]
        return [IsAccountingManager()]

    def get_queryset(self):
        qs = ExpenseBudget.objects.select_related("expense_category")
        period = self.request.query_params.get("fiscal_period_id")
        if period:
            qs = qs.filter(fiscal_period_id=period)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.id)


class CorporateCardTransactionViewSet(ModelViewSet):
    serializer_class = CorporateCardTransactionSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAccountingViewer()]
        return [IsAccountingManager()]

    def get_queryset(self):
        qs = CorporateCardTransaction.objects.select_related("currency")
        employee = self.request.query_params.get("employee")
        reconciled = self.request.query_params.get("reconciled")
        if employee:
            qs = qs.filter(employee=employee)
        if reconciled is not None:
            qs = qs.filter(reconciled=reconciled.lower() == "true")
        return qs


# -------------------------------------------------------------------------
# Report views
# -------------------------------------------------------------------------

class ExpenseReportsViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsAccountingViewer]
    queryset = ExpenseTransaction.objects.none()
    serializer_class = ExpenseTransactionSerializer

    @action(detail=False, methods=["get"], url_path="analysis")
    def analysis(self, request):
        start = request.query_params.get("start_date")
        end = request.query_params.get("end_date")
        branch = request.query_params.get("branch")
        from datetime import date
        return Response(generate_expense_analysis(
            start_date=date.fromisoformat(start),
            end_date=date.fromisoformat(end),
            branch=branch,
        ))

    @action(detail=False, methods=["get"], url_path="department")
    def by_department(self, request):
        return Response(generate_department_expense_report(
            start_date=date.fromisoformat(request.query_params["start_date"]),
            end_date=date.fromisoformat(request.query_params["end_date"]),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="project")
    def by_project(self, request):
        return Response(generate_project_expense_report(
            start_date=date.fromisoformat(request.query_params["start_date"]),
            end_date=date.fromisoformat(request.query_params["end_date"]),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="budget-variance")
    def budget_variance(self, request):
        return Response(generate_budget_variance_report(
            fiscal_period_id=UUID(request.query_params["fiscal_period_id"]),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="prepaid")
    def prepaid(self, request):
        return Response(generate_prepaid_expense_report(
            as_of_date=date.fromisoformat(request.query_params.get("as_of_date", str(date.today()))),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="aging")
    def aging(self, request):
        return Response(generate_expense_aging_report(
            as_of_date=date.fromisoformat(request.query_params.get("as_of_date", str(date.today()))),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="employee-claims")
    def employee_claims(self, request):
        return Response(generate_employee_claims_report(
            start_date=date.fromisoformat(request.query_params["start_date"]),
            end_date=date.fromisoformat(request.query_params["end_date"]),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="trend")
    def trend(self, request):
        return Response(generate_expense_trend_report(
            start_date=date.fromisoformat(request.query_params["start_date"]),
            end_date=date.fromisoformat(request.query_params["end_date"]),
            branch=request.query_params.get("branch"),
        ))

    @action(detail=False, methods=["get"], url_path="tax")
    def tax(self, request):
        return Response(generate_tax_deduction_report(
            start_date=date.fromisoformat(request.query_params["start_date"]),
            end_date=date.fromisoformat(request.query_params["end_date"]),
            branch=request.query_params.get("branch"),
        ))
