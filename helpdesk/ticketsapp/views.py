import json
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from .models import Ticket, AuditLog, Profile, Comment, Attachment
from .forms import CommentForm, AttachmentForm
from .rbac import get_user_role, can_view_ticket, can_update_ticket, can_change_status, IssueReporterRequiredMixin, ProjectManagerRequiredMixin

def custom_login(request):
    """Custom login view for the application"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            role = get_user_role(user)
            if role is None:
                default_role = 'PROJECT_MANAGER' if (user.is_superuser or user.is_staff) else 'ISSUE_REPORTER'
                Profile.objects.update_or_create(user=user, defaults={'role': default_role})
                role = default_role
            
            # Redirect based on user role
            if role == 'ISSUE_REPORTER':
                return redirect('ir_dashboard')
            elif role == 'PROJECT_MANAGER':
                return redirect('pm_dashboard')
            elif role == 'SUPPORT_ENGINEER':
                return redirect('se_dashboard')
            else:
                return redirect('ticket_list')
        else:
            messages.error(request, "Invalid username or password")
    
    return render(request, 'ticketsapp/login.html')

def custom_logout(request):
    """Logout view"""
    # Capture role before logging out to hint the login UI
    prev_role = None
    if request.user.is_authenticated:
        prev_role = get_user_role(request.user)

    logout(request)
    messages.success(request, "You have been logged out successfully")

    login_url = reverse('login')
    if prev_role == 'ISSUE_REPORTER':
        return redirect(f"{login_url}?role=ir")
    elif prev_role == 'SUPPORT_ENGINEER':
        return redirect(f"{login_url}?role=se")
    elif prev_role == 'PROJECT_MANAGER':
        return redirect(f"{login_url}?role=pm")
    return redirect(login_url)

def register(request):
    """User registration view"""
    # Only Issue Reporters and Support Engineers can self-register.
    # Project Manager accounts must be promoted manually by an admin.
    role_map = {
        'ir': 'ISSUE_REPORTER',
        'se': 'SUPPORT_ENGINEER',
    }
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        selected_role = role_map.get(request.POST.get('role'))
        email = request.POST.get('email', '').strip()

        if not selected_role:
            messages.error(request, "Please select a valid role.")
        elif not email:
            messages.error(request, "Email is required.")
        elif form.is_valid():
            user = form.save(commit=False)
            user.email = email
            user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={'role': selected_role}
            )
            username = form.cleaned_data.get('username')
            messages.success(request, f"Account created for {username}. You can now log in.")
            role_hint = 'ir' if selected_role == 'ISSUE_REPORTER' else 'se'
            return redirect(f"{reverse('login')}?role={role_hint}")
    else:
        form = UserCreationForm()
    
    return render(request, 'ticketsapp/register.html', {'form': form})

def password_reset(request):
    """Password reset view"""
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                subject_template_name='ticketsapp/password_reset_subject.txt',
                email_template_name='ticketsapp/password_reset_email.html',
            )
            return redirect('password_reset_done')
    else:
        form = PasswordResetForm()
    
    return render(request, 'ticketsapp/password_reset.html', {'form': form})

def password_reset_done(request):
    """Password reset done view"""
    return render(request, 'ticketsapp/password_reset_done.html')

@login_required
def ir_dashboard(request):
    """Dashboard for Issue Reporters"""
    if get_user_role(request.user) != 'ISSUE_REPORTER':
        return HttpResponseForbidden("Access denied")
    
    tickets = Ticket.objects.filter(created_by=request.user).order_by('-created_at')
    # Ensure Est. Resolution displays even if missing in older tickets
    now = timezone.now()
    for t in tickets:
        t.sla_display = t.sla_due_at or compute_sla_due(t.created_at or now, t.category, t.priority)
    # Status counts for stat cards
    context = {
        'tickets': tickets,
        'all_tickets_count': tickets.count(),
        'pending_tickets_count': tickets.filter(status='NEW').count(),
        'in_progress_tickets_count': tickets.filter(status='IN_PROGRESS').count(),
        'resolved_tickets_count': tickets.filter(status='RESOLVED').count(),
        'cancelled_tickets_count': tickets.filter(status='CLOSED').count(),
    }
    return render(request, 'ticketsapp/ir_dashboard.html', context)

@login_required
def pm_dashboard(request):
    """Dashboard for Project Managers"""
    if get_user_role(request.user) != 'PROJECT_MANAGER':
        return HttpResponseForbidden("Access denied")

    unassigned_qs = Ticket.objects.filter(assigned_to__isnull=True).order_by('-created_at')
    all_tickets = Ticket.objects.all().order_by('-updated_at')
    # Annotate tickets with SLA remaining and state for UI badges
    now = timezone.now()
    def humanize_delta(delta):
        seconds = int(abs(delta.total_seconds()))
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if not days and not hours:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return ", ".join(parts[:2])
    for t in all_tickets:
        if t.sla_due_at:
            delta = t.sla_due_at - now
            if delta.total_seconds() < 0:
                t.sla_state = 'overdue'
                t.sla_remaining_display = f"overdue by {humanize_delta(-delta)}"
            elif delta.total_seconds() < 86400:
                t.sla_state = 'due_today'
                t.sla_remaining_display = f"due in {humanize_delta(delta)}"
            else:
                t.sla_state = 'future'
                t.sla_remaining_display = f"due in {humanize_delta(delta)}"
    # Only include users who have logged in
    support_engineers = User.objects.filter(profile__role='SUPPORT_ENGINEER', last_login__isnull=False)
    issue_reporters = User.objects.filter(profile__role='ISSUE_REPORTER', last_login__isnull=False)

    support_team = []
    for u in support_engineers:
        name = u.get_full_name() or u.username
        initials = ''.join([part[0] for part in (u.get_full_name() or u.username).split()][:2]).upper()
        support_team.append({
            'id': u.id,
            'name': name,
            'initials': initials if initials else name[:2].upper(),
            'role': 'Support Engineer',
            'ticket_count': Ticket.objects.filter(assigned_to=u).count(),
            'workload': min(100, Ticket.objects.filter(assigned_to=u, status='IN_PROGRESS').count() * 10),
        })

    # Build issue reporter summaries
    reporters = []
    for u in issue_reporters:
        name = u.get_full_name() or u.username
        initials = ''.join([part[0] for part in (u.get_full_name() or u.username).split()][:2]).upper()
        reporters.append({
            'id': u.id,
            'name': name,
            'initials': initials if initials else name[:2].upper(),
            'role': 'Issue Reporter',
            'ticket_count': Ticket.objects.filter(created_by=u).count(),
            'last_login': u.last_login,
        })

    context = {
        'unassigned_tickets_list': unassigned_qs,
        'all_tickets': all_tickets,
        'total_tickets': Ticket.objects.count(),
        'unassigned_tickets': unassigned_qs.count(),
        'in_progress_tickets': Ticket.objects.filter(status='IN_PROGRESS').count(),
        'resolved_tickets': Ticket.objects.filter(status='RESOLVED').count(),
        'rejected_tickets': Ticket.objects.filter(status='CLOSED').count(),
        'ticket_change': 0,
        'unassigned_change': 0,
        'progress_change': 0,
        'resolved_change': 0,
        'support_team': support_team,
        'issue_reporters': reporters,
    }

    return render(request, 'ticketsapp/pm_dashboard.html', context)

@login_required
def pm_users(request):
    """Users page for Project Managers: show logged-in Support Engineers and Issue Reporters"""
    if get_user_role(request.user) != 'PROJECT_MANAGER':
        return HttpResponseForbidden("Access denied")

    support_engineers = User.objects.filter(profile__role='SUPPORT_ENGINEER', last_login__isnull=False)
    issue_reporters = User.objects.filter(profile__role='ISSUE_REPORTER', last_login__isnull=False)

    support_team = []
    for u in support_engineers:
        name = u.get_full_name() or u.username
        initials = ''.join([part[0] for part in (u.get_full_name() or u.username).split()][:2]).upper()
        support_team.append({
            'id': u.id,
            'name': name,
            'initials': initials if initials else name[:2].upper(),
            'role': 'Support Engineer',
            'ticket_count': Ticket.objects.filter(assigned_to=u).count(),
            'workload': min(100, Ticket.objects.filter(assigned_to=u, status='IN_PROGRESS').count() * 10),
            'last_login': u.last_login,
        })

    reporters = []
    for u in issue_reporters:
        name = u.get_full_name() or u.username
        initials = ''.join([part[0] for part in (u.get_full_name() or u.username).split()][:2]).upper()
        reporters.append({
            'id': u.id,
            'name': name,
            'initials': initials if initials else name[:2].upper(),
            'role': 'Issue Reporter',
            'ticket_count': Ticket.objects.filter(created_by=u).count(),
            'last_login': u.last_login,
        })

    context = {
        'support_team': support_team,
        'issue_reporters': reporters,
    }

    return render(request, 'ticketsapp/pm_users.html', context)

@login_required
def pm_sla(request):
    """SLA Alerts page for Project Managers"""
    if get_user_role(request.user) != 'PROJECT_MANAGER':
        return HttpResponseForbidden("Access denied")

    def humanize_delta(delta):
        """Return a short human string like '2 days, 3 hours' or '45 minutes'."""
        seconds = int(abs(delta.total_seconds()))
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if not days and not hours:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return ", ".join(parts[:2])

    now = timezone.now()
    # Optional backfill: auto-set SLA dates for tickets missing them
    if request.method == 'POST' and request.POST.get('autofill') == '1':
        missing_qs = Ticket.objects.filter(sla_due_at__isnull=True).exclude(status__in=['RESOLVED','CLOSED'])
        updated = 0
        for t in missing_qs:
            try:
                due = compute_sla_due(t.created_at or now, t.category, t.priority)
                t.sla_due_at = due
                t.save(update_fields=['sla_due_at'])
                updated += 1
            except Exception:
                pass
        messages.success(request, f"Auto-set SLA dates for {updated} ticket(s)")
        return redirect('pm_sla')
    # Overdue: sla_due_at passed and not resolved/closed
    overdue = Ticket.objects.filter(sla_due_at__lt=now).exclude(status__in=['RESOLVED','CLOSED'])
    # Due today
    start_today = timezone.datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    end_today = start_today + timezone.timedelta(days=1)
    due_today = Ticket.objects.filter(sla_due_at__gte=start_today, sla_due_at__lt=end_today).exclude(status__in=['RESOLVED','CLOSED'])
    # Due in next 24 hours
    next_24h = Ticket.objects.filter(sla_due_at__gte=now, sla_due_at__lt=now + timezone.timedelta(hours=24)).exclude(status__in=['RESOLVED','CLOSED'])
    # Missing SLA
    missing_sla = Ticket.objects.filter(sla_due_at__isnull=True).exclude(status__in=['RESOLVED','CLOSED'])
    missing_count = missing_sla.count()

    alerts = []
    for t in overdue:
        overdue_by = humanize_delta(now - (t.sla_due_at or now))
        alerts.append({
            'critical': True,
            'title': f"Overdue SLA — #{t.ticket_id}",
            'description': f"{t.title} overdue by {overdue_by}.",
            'ticket_pk': t.pk,
        })
    for t in due_today:
        remaining = humanize_delta((t.sla_due_at or now) - now)
        alerts.append({
            'critical': True,
            'title': f"Due Today — #{t.ticket_id}",
            'description': f"{t.title} due today in {remaining}.",
            'ticket_pk': t.pk,
        })
    for t in next_24h:
        remaining = humanize_delta((t.sla_due_at or now) - now)
        alerts.append({
            'critical': False,
            'title': f"Due in 24h — #{t.ticket_id}",
            'description': f"{t.title} expiring in {remaining}.",
            'ticket_pk': t.pk,
        })
    for t in missing_sla:
        alerts.append({
            'critical': False,
            'title': f"Missing SLA — #{t.ticket_id}",
            'description': f"{t.title} has no SLA date set.",
            'ticket_pk': t.pk,
        })

    # Sort alerts: critical first, then by nearest due time
    alerts.sort(key=lambda a: (not a['critical'], a['title']))

    return render(request, 'ticketsapp/pm_sla.html', { 'sla_alerts': alerts, 'missing_count': missing_count })

@login_required
def se_dashboard(request):
    """Dashboard for Support Engineers"""
    if get_user_role(request.user) != 'SUPPORT_ENGINEER':
        return HttpResponseForbidden("Access denied")
    
    # Show assigned tickets that are either pending (NEW) or in progress
    tickets = Ticket.objects.filter(assigned_to=request.user, status__in=['NEW','IN_PROGRESS']).order_by('-assigned_at')

    # SLA alerts for the assigned tickets
    now = timezone.now()
    def humanize_delta(delta):
        seconds = int(abs(delta.total_seconds()))
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if days:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if not days and not hours:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        return ", ".join(parts[:2])

    overdue = tickets.filter(sla_due_at__lt=now)
    start_today = timezone.datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
    end_today = start_today + timezone.timedelta(days=1)
    due_today = tickets.filter(sla_due_at__gte=start_today, sla_due_at__lt=end_today)
    next_24h = tickets.filter(sla_due_at__gte=now, sla_due_at__lt=now + timezone.timedelta(hours=24))

    # Annotate each ticket with SLA remaining/state for table badges
    for t in tickets:
        if t.sla_due_at:
            delta = t.sla_due_at - now
            if delta.total_seconds() < 0:
                t.sla_state = 'overdue'
                t.sla_remaining_display = f"overdue by {humanize_delta(-delta)}"
            elif delta.total_seconds() < 86400:
                t.sla_state = 'due_today'
                t.sla_remaining_display = f"due in {humanize_delta(delta)}"
            else:
                t.sla_state = 'future'
                t.sla_remaining_display = f"due in {humanize_delta(delta)}"

    sla_alerts = []
    for t in overdue:
        overdue_by = humanize_delta(now - (t.sla_due_at or now))
        sla_alerts.append({
            'critical': True,
            'title': f"Overdue SLA — #{t.ticket_id}",
            'description': f"{t.title} overdue by {overdue_by}.",
            'ticket_pk': t.pk,
        })
    for t in due_today:
        remaining = humanize_delta((t.sla_due_at or now) - now)
        sla_alerts.append({
            'critical': True,
            'title': f"Due Today — #{t.ticket_id}",
            'description': f"{t.title} due today in {remaining}.",
            'ticket_pk': t.pk,
        })
    for t in next_24h:
        remaining = humanize_delta((t.sla_due_at or now) - now)
        sla_alerts.append({
            'critical': False,
            'title': f"Due in 24h — #{t.ticket_id}",
            'description': f"{t.title} expiring in {remaining}.",
            'ticket_pk': t.pk,
        })

    # Sort alerts consistently: critical first, then by ticket id
    sla_alerts.sort(key=lambda a: (not a['critical'], a['title']))

    return render(request, 'ticketsapp/se_dashboard.html', {'tickets': tickets, 'sla_alerts': sla_alerts})

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'ticketsapp/ticket_list.html'
    context_object_name = 'tickets'
    ordering = ['-created_at']
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        role = get_user_role(user)
        if role == 'PROJECT_MANAGER':
            return Ticket.objects.all().order_by('-created_at')
        if role == 'SUPPORT_ENGINEER':
            return Ticket.objects.filter(assigned_to=user).order_by('-created_at')
        if role == 'ISSUE_REPORTER':
            return Ticket.objects.filter(created_by=user).order_by('-created_at')
        return Ticket.objects.none()


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'ticketsapp/ticket_detail.html'
    context_object_name = 'ticket'

    def get_object(self, queryset=None):
        ticket = super().get_object(queryset)
        if not can_view_ticket(self.request.user, ticket):
            raise PermissionDenied
        return ticket

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comment_form'] = CommentForm()
        context['attachment_form'] = AttachmentForm()
        context['comments'] = self.object.comments.order_by('-created_at')
        context['attachments'] = self.object.attachments.order_by('-uploaded_at')
        return context


class TicketCreateView(IssueReporterRequiredMixin, CreateView):
    model = Ticket
    template_name = 'ticketsapp/ticket_form.html'
    fields = ['title', 'description', 'priority', 'category']
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'NEW'
        # Auto-set SLA due based on category/priority
        now = timezone.now()
        category = (form.cleaned_data.get('category') or '').upper()
        priority = (form.cleaned_data.get('priority') or '').upper()

        def add_business_days(start_dt, days):
            dt = start_dt
            added = 0
            while added < days:
                dt += timezone.timedelta(days=1)
                # Monday=0 ... Sunday=6
                if dt.weekday() < 5:
                    added += 1
            return dt

        # Map categories/priorities to SLA windows
        # Critical: urgent priority or network category → 4 hours (latest in 2–4h range)
        if priority == 'URGENT' or category == 'NETWORK':
            form.instance.sla_due_at = now + timezone.timedelta(hours=4)
        # Hardware → 1–3 business days → use 3
        elif category == 'HARDWARE':
            form.instance.sla_due_at = add_business_days(now, 3)
        # Software/Access → 1–2 business days → use 2
        elif category in ('SOFTWARE', 'ACCESS'):
            form.instance.sla_due_at = add_business_days(now, 2)
        # General inquiries/Other → 1–5 business days → use 5
        else:
            form.instance.sla_due_at = add_business_days(now, 5)
        response = super().form_valid(form)
        attachment = self.request.FILES.get('attachment')
        if attachment:
            Attachment.objects.create(
                ticket=self.object,
                uploaded_by=self.request.user,
                file=attachment
            )
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'redirect_url': self.object.get_absolute_url(),
                'ticket_id': self.object.ticket_id
            })
        return response


class EmergencyTicketCreateView(ProjectManagerRequiredMixin, CreateView):
    model = Ticket
    template_name = 'ticketsapp/pm_emergency_form.html'
    fields = ['title', 'description', 'priority', 'category', 'reporter_name']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = 'NEW'
        now = timezone.now()
        category = (form.cleaned_data.get('category') or '').upper()
        priority = (form.cleaned_data.get('priority') or '').upper()

        def add_business_days(start_dt, days):
            dt = start_dt
            added = 0
            while added < days:
                dt += timezone.timedelta(days=1)
                if dt.weekday() < 5:
                    added += 1
            return dt

        if priority == 'URGENT' or category == 'NETWORK':
            form.instance.sla_due_at = now + timezone.timedelta(hours=4)
        elif category == 'HARDWARE':
            form.instance.sla_due_at = add_business_days(now, 3)
        elif category in ('SOFTWARE', 'ACCESS'):
            form.instance.sla_due_at = add_business_days(now, 2)
        else:
            form.instance.sla_due_at = add_business_days(now, 5)
        messages.success(self.request, 'Emergency ticket created successfully.')
        return super().form_valid(form)


class TicketUpdateView(LoginRequiredMixin, UpdateView):
    model = Ticket
    template_name = 'ticketsapp/ticket_form.html'
    fields = ['title', 'description', 'priority', 'category', 'status']

    def get_object(self, queryset=None):
        ticket = super().get_object(queryset)
        if not can_update_ticket(self.request.user, ticket):
            raise PermissionDenied
        return ticket

    def form_valid(self, form):
        original_ticket = Ticket.objects.get(pk=form.instance.pk)
        new_status = form.cleaned_data.get('status')
        if new_status and new_status != original_ticket.status:
            if not can_change_status(self.request.user, original_ticket, new_status):
                messages.error(self.request, "You don't have permission to change the ticket to the selected status.")
                return redirect('ticket_detail', pk=original_ticket.pk)
        # Recalculate SLA when category or priority changes
        new_category = form.cleaned_data.get('category')
        new_priority = form.cleaned_data.get('priority')
        if new_category != original_ticket.category or new_priority != original_ticket.priority:
            form.instance.sla_due_at = compute_sla_due(timezone.now(), new_category, new_priority)
        return super().form_valid(form)

@login_required
def add_comment(request, ticket_id):
    """Add comment to a ticket"""
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("Access denied")
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Comment.objects.create(
                ticket=ticket,
                created_by=request.user,
                text=content
            )
            messages.success(request, "Comment added successfully")
        return redirect('ticket_detail', pk=ticket_id)
    return redirect('ticket_detail', pk=ticket_id)

@login_required
def add_attachment(request, ticket_id):
    """Add attachment to a ticket"""
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if not can_view_ticket(request.user, ticket):
        return HttpResponseForbidden("Access denied")
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        Attachment.objects.create(
            ticket=ticket,
            uploaded_by=request.user,
            file=file
        )
        messages.success(request, "Attachment added successfully")
    return redirect('ticket_detail', pk=ticket_id)

@login_required
def assign_ticket(request, pk):
    """View for Project Manager to assign tickets to Support Engineers"""
    if get_user_role(request.user) != 'PROJECT_MANAGER':
        return HttpResponseForbidden("Access denied")
    
    ticket = get_object_or_404(Ticket, pk=pk)
    support_engineers = User.objects.filter(profile__role='SUPPORT_ENGINEER')
    
    if request.method == 'POST':
        engineer_id = request.POST.get('support_engineer')
        notes = request.POST.get('notes', '')
        
        if engineer_id:
            engineer = get_object_or_404(User, pk=engineer_id)
            ticket.assigned_to = engineer
            ticket.assigned_at = timezone.now()
            ticket.status = 'IN_PROGRESS'
            ticket.save()
            
            # Create audit log entry
            meta_payload = {
                "assigned_to": engineer.username,
                "notes": notes or ""
            }
            AuditLog.objects.create(
                ticket=ticket,
                action=f"Assigned ticket to {engineer.username}",
                performed_by=request.user,
                meta=json.dumps(meta_payload)
            )
            
            # Send notification (placeholder for actual notification)
            # notifications.notify_assignment(ticket, engineer, request.user)
            
            messages.success(request, f"Ticket #{ticket.ticket_id} successfully assigned to {engineer.username}")
            return redirect('pm_dashboard')
        else:
            messages.error(request, "Please select a support engineer")
    
    context = {
        'ticket': ticket,
        'support_engineers': support_engineers,
    }
    
    return render(request, 'ticketsapp/assign_ticket.html', context)
def _add_business_days(start_dt, days):
    dt = start_dt
    added = 0
    while added < days:
        dt += timezone.timedelta(days=1)
        if dt.weekday() < 5:  # Mon-Fri
            added += 1
    return dt

def compute_sla_due(start_dt, category, priority):
    """Compute SLA due datetime based on category/priority and a start timestamp."""
    category = (category or '').upper()
    priority = (priority or '').upper()
    # Critical: urgent priority or network category → up to 4 hours
    if priority == 'URGENT' or category == 'NETWORK':
        return start_dt + timezone.timedelta(hours=4)
    # Hardware → up to 3 business days
    if category == 'HARDWARE':
        return _add_business_days(start_dt, 3)
    # Software/Access → up to 2 business days
    if category in ('SOFTWARE', 'ACCESS'):
        return _add_business_days(start_dt, 2)
    # General/Other → up to 5 business days
    return _add_business_days(start_dt, 5)
