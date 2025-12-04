from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import api

# API router setup
router = DefaultRouter()
router.register(r'tickets', api.TicketViewSet, basename='api-ticket')
router.register(r'comments', api.CommentViewSet, basename='api-comment')
router.register(r'attachments', api.AttachmentViewSet, basename='api-attachment')

urlpatterns = [
    # Authentication
    path('', views.custom_login, name='login'),
    path('login/', views.custom_login, name='login_alt'),
    path('register/', views.register, name='register'),
    path('logout/', views.custom_logout, name='logout'),
    path('password-reset/', views.password_reset, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    
    # Dashboards
    path('dashboard/ir/', views.ir_dashboard, name='ir_dashboard'),
    path('dashboard/pm/', views.pm_dashboard, name='pm_dashboard'),
    path('dashboard/pm/users/', views.pm_users, name='pm_users'),
    path('dashboard/pm/sla/', views.pm_sla, name='pm_sla'),
    path('dashboard/se/', views.se_dashboard, name='se_dashboard'),
    # Add aliases for the dashboards that were being accessed
    path('ir-dashboard/', views.ir_dashboard, name='ir_dashboard_alt'),
    path('pm-dashboard/', views.pm_dashboard, name='pm_dashboard_alt'),
    path('se-dashboard/', views.se_dashboard, name='se_dashboard_alt'),
    
    # Ticket web views
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/create/', views.TicketCreateView.as_view(), name='ticket_create'),
    path('tickets/emergency/create/', views.EmergencyTicketCreateView.as_view(), name='pm_emergency_create'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/update/', views.TicketUpdateView.as_view(), name='ticket_update'),
    path('tickets/<int:pk>/assign/', views.assign_ticket, name='assign_ticket'),
    
    # Comments and attachments
    path('tickets/<int:ticket_id>/comment/', views.add_comment, name='add_comment'),
    path('tickets/<int:ticket_id>/attachment/', views.add_attachment, name='add_attachment'),
    
    # API endpoints
    path('api/', include(router.urls)),
]
