from django.urls import path

from .views import (
    LocalPurchaseOrderDetailView,
    LocalPurchaseOrderItemDetailView,
    LocalPurchaseOrderItemListCreateView,
    LocalPurchaseOrderListCreateView,
    LocalPurchaseOrderReceiveView,
    LocalPurchaseOrderTransitionView,
    SupplierDetailView,
    SupplierListCreateView,
)

app_name = 'suppliers'

urlpatterns = [
    path(
        'lpos/<uuid:lpo_pk>/items/<uuid:pk>/',
        LocalPurchaseOrderItemDetailView.as_view(),
        name='lpo-item-detail',
    ),
    path(
        'lpos/<uuid:lpo_pk>/items/',
        LocalPurchaseOrderItemListCreateView.as_view(),
        name='lpo-item-list-create',
    ),
    path(
        'lpos/<uuid:pk>/transition/',
        LocalPurchaseOrderTransitionView.as_view(),
        name='lpo-transition',
    ),
    path(
        'lpos/<uuid:pk>/receive/',
        LocalPurchaseOrderReceiveView.as_view(),
        name='lpo-receive',
    ),
    path('lpos/<uuid:pk>/', LocalPurchaseOrderDetailView.as_view(), name='lpo-detail'),
    path('lpos/', LocalPurchaseOrderListCreateView.as_view(), name='lpo-list-create'),
    path('<uuid:pk>/', SupplierDetailView.as_view(), name='supplier-detail'),
    path('', SupplierListCreateView.as_view(), name='supplier-list-create'),
]
