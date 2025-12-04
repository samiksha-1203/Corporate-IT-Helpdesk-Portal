from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps
from .models import Profile, Ticket

def get_user_role(user):
    """Get the role of a user from their profile.
    Superusers/staff automatically behave as Project Managers
    if no explicit profile has been assigned yet."""
    try:
        return user.profile.role
    except (Profile.DoesNotExist, AttributeError):
        if user.is_superuser or user.is_staff:
            return 'PROJECT_MANAGER'
        return None

# Role-based decorators
def project_manager_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if get_user_role(request.user) == 'PROJECT_MANAGER':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def support_engineer_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if get_user_role(request.user) == 'SUPPORT_ENGINEER':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def issue_reporter_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if get_user_role(request.user) == 'ISSUE_REPORTER':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

# Mixins for class-based views
class ProjectManagerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and get_user_role(self.request.user) == 'PROJECT_MANAGER'

class SupportEngineerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and get_user_role(self.request.user) == 'SUPPORT_ENGINEER'

class IssueReporterRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and get_user_role(self.request.user) == 'ISSUE_REPORTER'

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        role = get_user_role(self.request.user)
        if role is None and not (self.request.user.is_staff or self.request.user.is_superuser):
            Profile.objects.update_or_create(
                user=self.request.user,
                defaults={'role': 'ISSUE_REPORTER'}
            )
            return redirect(self.request.path)
        messages.error(self.request, "Only Issue Reporters can create tickets.", extra_tags='role_mismatch')
        if role == 'PROJECT_MANAGER':
            return redirect('pm_dashboard')
        elif role == 'SUPPORT_ENGINEER':
            return redirect('se_dashboard')
        return redirect('ticket_list')

# Permission check functions
def can_view_ticket(user, ticket):
    """Check if a user can view a specific ticket."""
    role = get_user_role(user)

    # Graceful fallback: if role is missing, allow viewing own or assigned tickets
    if role is None:
        if user.is_superuser or user.is_staff:
            return True
        return ticket.created_by == user or ticket.assigned_to == user

    if role == 'PROJECT_MANAGER':
        return True
    elif role == 'SUPPORT_ENGINEER':
        return ticket.assigned_to == user
    elif role == 'ISSUE_REPORTER':
        return ticket.created_by == user
    return False

def can_update_ticket(user, ticket):
    """Check if a user can update a specific ticket."""
    role = get_user_role(user)
    
    if role == 'PROJECT_MANAGER':
        return True
    elif role == 'SUPPORT_ENGINEER':
        return ticket.assigned_to == user
    elif role == 'ISSUE_REPORTER':
        # Issue reporters can only update their own tickets before they're assigned
        return ticket.created_by == user and ticket.assigned_to is None
    return False

def can_assign_ticket(user):
    """Check if a user can assign tickets."""
    return get_user_role(user) == 'PROJECT_MANAGER'

def can_change_status(user, ticket, new_status):
    """Check if a user can change a ticket's status to the new status."""
    role = get_user_role(user)
    current_status = ticket.status
    
    if role == 'PROJECT_MANAGER':
        # Project managers can make any status change
        return True
    elif role == 'SUPPORT_ENGINEER':
        # Support engineers can progress work on their assigned tickets
        if ticket.assigned_to != user:
            return False
        # Allow moving from pending (NEW) to working or directly resolved
        if current_status == 'NEW' and new_status in ('IN_PROGRESS', 'RESOLVED'):
            return True
        # Allow toggling between in-progress and resolved
        if current_status == 'IN_PROGRESS' and new_status == 'RESOLVED':
            return True
        if current_status == 'RESOLVED' and new_status == 'IN_PROGRESS':
            return True
        return False
    elif role == 'ISSUE_REPORTER':
        # Issue reporters can only change from RESOLVED to CLOSED
        return current_status == 'RESOLVED' and new_status == 'CLOSED' and ticket.created_by == user
    return False
