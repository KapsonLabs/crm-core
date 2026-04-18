from django.urls import path

from .views import (
    ProductListCreateView,
    ProductDetailView,
    JobListCreateView,
    JobDetailView,
    JobAssignView,
    JobAssignmentDetailView,
    JobCompleteView,
    JobCloseView,
)

app_name = 'jobs'

urlpatterns = [
    path('products/', ProductListCreateView.as_view(), name='product-list-create'),
    path('products/<uuid:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('<uuid:job_pk>/assign/', JobAssignView.as_view(), name='job-assign'),
    path('<uuid:job_pk>/complete/', JobCompleteView.as_view(), name='job-complete'),
    path('<uuid:job_pk>/close/', JobCloseView.as_view(), name='job-close'),
    path('list/', JobListCreateView.as_view(), name='job-list-create'),
    path('<uuid:pk>/', JobDetailView.as_view(), name='job-detail'),
    path('job-assignments/<uuid:pk>/', JobAssignmentDetailView.as_view(), name='job-assignment-detail'),
]
