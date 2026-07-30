from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_view, name='upload'),
    path('dashboard/<int:pk>/', views.dashboard_view, name='dashboard'),
    path('insights/<int:pk>/', views.insights_view, name='insights'),
    path('history/', views.history_view, name='history'),
    # API endpoints
    path('api/analysis/<int:pk>/', views.api_analysis, name='api_analysis'),
    path('api/charts/<int:pk>/', views.api_charts, name='api_charts'),
    path('api/kpis/<int:pk>/', views.api_kpis, name='api_kpis'),
    path('api/insights/<int:pk>/', views.api_insights, name='api_insights'),
    path('export/<int:pk>/', views.export_excel_view, name='export_excel'),
]
