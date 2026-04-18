from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('totals/', views.AnalyticsTotalsView.as_view(), name='analytics-totals'),
    path(
        'monthly/', views.AnalyticsMonthlyRevenueExpenditureView.as_view(),
        name='analytics-monthly',
    ),
    path('top-selling/', views.AnalyticsTopSellingView.as_view(), name='analytics-top-selling'),
    path('time-to-service/',
        views.AnalyticsAverageTimeToServiceView.as_view(),
        name='analytics-avg-time',
    ),
]
