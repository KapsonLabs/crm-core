from django.urls import path

from .views import (
    BankAccountDetailView,
    BankAccountListCreateView,
    InvoiceListCreateView,
    InvoiceDetailView,
    InvoiceVoidView,
    InvoicePaymentListCreateView,
    PaymentDetailView,
    PaymentMethodListCreateView,
    PaymentMethodDetailView,
    RequisitionListCreateView,
    RequisitionDetailView,
)

app_name = 'financials'

urlpatterns = [
    path('invoices/<uuid:pk>/void/', InvoiceVoidView.as_view(), name='invoice-void'),
    path('invoices/<uuid:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/', InvoiceListCreateView.as_view(), name='invoice-list-create'),
    path('payments/', InvoicePaymentListCreateView.as_view(), name='invoice-payment-list-create'),
    path('payments/<uuid:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('payment-methods/<uuid:pk>/', PaymentMethodDetailView.as_view(), name='payment-method-detail'),
    path('payment-methods/', PaymentMethodListCreateView.as_view(), name='payment-method-list-create'),
    path('bank-accounts/<uuid:pk>/', BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('bank-accounts/', BankAccountListCreateView.as_view(), name='bank-account-list-create'),
    path('requisitions/<uuid:pk>/', RequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/', RequisitionListCreateView.as_view(), name='requisition-list-create'),
]