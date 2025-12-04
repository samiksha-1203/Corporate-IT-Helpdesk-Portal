from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from .models import Profile, Ticket

def get_project_managers_emails():
    """Get email addresses of all project managers"""
    pm_profiles = Profile.objects.filter(role='PROJECT_MANAGER')
    pm_emails = [profile.user.email for profile in pm_profiles if profile.user.email]
    return pm_emails

def notify_ticket_assigned(ticket):
    """Send notification when a ticket is assigned to a support engineer"""
    if not ticket.assigned_to or not ticket.assigned_to.email:
        return
    
    subject = f'Ticket #{ticket.ticket_id} has been assigned to you'
    message = f"""
    Hello {ticket.assigned_to.get_full_name() or ticket.assigned_to.username},
    
    You have been assigned to ticket #{ticket.ticket_id}: {ticket.title}
    
    Priority: {ticket.get_priority_display()}
    Category: {ticket.category}
    Description: {ticket.description}
    
    Please review and update the status as needed.
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [ticket.assigned_to.email],
        fail_silently=True,
    )

def notify_status_change(ticket, previous_status):
    """Send notification when a ticket status changes"""
    recipients = []
    
    # Add ticket creator
    if ticket.created_by and ticket.created_by.email:
        recipients.append(ticket.created_by.email)
    
    # Add assigned engineer if exists
    if ticket.assigned_to and ticket.assigned_to.email:
        recipients.append(ticket.assigned_to.email)
    
    # Add all project managers
    recipients.extend(get_project_managers_emails())
    
    # Remove duplicates
    recipients = list(set(recipients))
    
    if not recipients:
        return
    
    subject = f'Ticket #{ticket.ticket_id} status changed: {previous_status} → {ticket.get_status_display()}'
    message = f"""
    Ticket #{ticket.ticket_id}: {ticket.title}
    
    Status has been changed from {previous_status} to {ticket.get_status_display()}
    
    Priority: {ticket.get_priority_display()}
    Category: {ticket.category}
    
    Created by: {ticket.created_by.get_full_name() or ticket.created_by.username}
    Assigned to: {ticket.assigned_to.get_full_name() or ticket.assigned_to.username if ticket.assigned_to else 'Unassigned'}
    """
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=True,
    )