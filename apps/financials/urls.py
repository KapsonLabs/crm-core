from django.urls import path

from .views import (
    InvoiceListCreateView,
    InvoiceDetailView,
    InvoiceVoidView,
    InvoicePaymentListCreateView,
    PaymentDetailView,
    RequisitionListCreateView,
    RequisitionDetailView,
)

app_name = 'financials'

urlpatterns = [
    path('invoices/<uuid:pk>/void/', InvoiceVoidView.as_view(), name='invoice-void'),
    path(
        'invoices/<uuid:invoice_pk>/payments/',
        InvoicePaymentListCreateView.as_view(),
        name='invoice-payment-list-create',
    ),
    path('invoices/<uuid:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/', InvoiceListCreateView.as_view(), name='invoice-list-create'),
    path('payments/<uuid:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('requisitions/<uuid:pk>/', RequisitionDetailView.as_view(), name='requisition-detail'),
    path('requisitions/', RequisitionListCreateView.as_view(), name='requisition-list-create'),
]
