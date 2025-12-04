from django.contrib import admin
from .models import Profile, Ticket, Comment, Attachment, AuditLog

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')  # shows these columns in admin
    search_fields = ('user__username',)
    list_filter = ('role',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'title', 'status', 'priority', 'category', 'created_by', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'category', 'created_at')
    search_fields = ('ticket_id', 'title', 'description', 'created_by__username', 'assigned_to__username')
    date_hierarchy = 'created_at'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('ticket__ticket_id', 'created_by__username', 'text')

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('ticket__ticket_id', 'uploaded_by__username', 'file')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('ticket__ticket_id', 'performed_by__username', 'action')
