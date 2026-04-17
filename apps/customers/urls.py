from django.urls import path

from .views import (
    CustomerListCreateView,
    CustomerDetailView,
    CustomerFeedbackListCreateView,
    CustomerFeedbackDetailView,
)

app_name = 'customers'

urlpatterns = [
    path('', CustomerListCreateView.as_view(), name='customer-list-create'),
    path('<uuid:pk>/', CustomerDetailView.as_view(), name='customer-detail'),
    path('feedback/', CustomerFeedbackListCreateView.as_view(), name='feedback-list-create'),
    path('feedback/<uuid:pk>/', CustomerFeedbackDetailView.as_view(), name='feedback-detail'),
]
