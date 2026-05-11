from rest_framework.routers import DefaultRouter

from apps.expense_accounting.api.views.expense_views import (
    CorporateCardTransactionViewSet,
    ExpenseBudgetViewSet,
    ExpenseCategoryViewSet,
    ExpenseReportsViewSet,
    ExpenseTransactionViewSet,
    PrepaidExpenseScheduleViewSet,
)

router = DefaultRouter()
router.register(r"expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register(r"expenses", ExpenseTransactionViewSet, basename="expense")
router.register(r"prepaid-schedules", PrepaidExpenseScheduleViewSet, basename="prepaid-schedule")
router.register(r"expense-budgets", ExpenseBudgetViewSet, basename="expense-budget")
router.register(r"corporate-cards", CorporateCardTransactionViewSet, basename="corporate-card")
router.register(r"expense-reports", ExpenseReportsViewSet, basename="expense-report")

urlpatterns = router.urls
