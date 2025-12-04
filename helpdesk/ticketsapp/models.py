from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
import random
import string
import json
from django.utils import timezone

def generate_ticket_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

class Profile(models.Model):
    ROLE_CHOICES = [
        ('PROJECT_MANAGER', 'Project Manager'),
        ('SUPPORT_ENGINEER', 'Support Engineer'),
        ('ISSUE_REPORTER', 'Issue Reporter'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('NEW', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Cancelled'),
    ]
    
    ticket_id = models.CharField(default=generate_ticket_id, max_length=10, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100)  # Keeping as CharField for simplicity
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tickets')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sla_due_at = models.DateTimeField(null=True, blank=True)
    # Optional free-text name when a PM raises a ticket on behalf of someone
    reporter_name = models.CharField(max_length=255, null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.ticket_id} - {self.title}"
    
    def assign_to(self, user):
        self.assigned_to = user
        self.assigned_at = timezone.now()
        self.save()

    def get_absolute_url(self):
        return reverse('ticket_detail', args=[self.pk])

class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment on {self.ticket.ticket_id} by {self.created_by.username}"

class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment for {self.ticket.ticket_id}"

class AuditLog(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=100)
    performed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    meta = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.action} on {self.ticket.ticket_id} by {self.performed_by.username}"
    
    def set_meta(self, data):
        self.meta = json.dumps(data)
        
    def get_meta(self):
        if self.meta:
            return json.loads(self.meta)
        return {}
