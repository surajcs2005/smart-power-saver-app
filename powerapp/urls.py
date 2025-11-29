from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('analytics/', views.analytics, name='analytics'),
    path('compare/', views.compare, name='compare'),
    path('control/', views.control, name='control'),
    path('rules/', views.rules, name='rules'),
    path('notifications/', views.notifications_page, name='notifications_page'),
    path('history/', views.history, name='history'),
    path('suggestions/', views.suggestions, name='suggestions'),
    path('management/', views.management, name='management'),
    path('login/', auth_views.LoginView.as_view(template_name='powerapp/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('settings/', views.settings, name='settings'),
    path('api/devices/', views.api_devices, name='api_devices'),
    path('api/toggle/<int:device_id>/', views.api_toggle_device, name='api_toggle_device'),
    path('api/reading/', views.api_post_reading, name='api_post_reading'),
    path('api/logs/<int:device_id>/', views.api_device_logs, name='api_device_logs'),
    path('api/usage/summary/', views.api_usage_summary, name='api_usage_summary'),
    path('api/compare/summary/', views.api_compare_summary, name='api_compare_summary'),
    path('api/heatmap/', views.api_heatmap, name='api_heatmap'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
    path('api/suggestions/', views.api_suggestions, name='api_suggestions'),
    path('api/chat/', views.api_chat, name='api_chat'),
]
