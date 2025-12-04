from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Profile, Ticket

class TicketSystemTests(TestCase):
    def setUp(self):
        # Create users with different roles
        self.pm_user = User.objects.create_user(username='pm_user', password='password123')
        self.ir_user = User.objects.create_user(username='ir_user', password='password123')
        self.se_user = User.objects.create_user(username='se_user', password='password123')
        
        # Ensure profiles exist with correct roles
        Profile.objects.update_or_create(user=self.pm_user, defaults={'role': 'PROJECT_MANAGER'})
        Profile.objects.update_or_create(user=self.ir_user, defaults={'role': 'ISSUE_REPORTER'})
        Profile.objects.update_or_create(user=self.se_user, defaults={'role': 'SUPPORT_ENGINEER'})
        
        # Create client
        self.client = Client()
    
    def test_ticket_creation_by_issue_reporter(self):
        """Test that an Issue Reporter can create a ticket"""
        self.client.login(username='ir_user', password='password123')
        
        # Create a ticket
        response = self.client.post(reverse('ticket_create'), {
            'title': 'Test Ticket',
            'description': 'This is a test ticket',
            'category': 'Hardware',
            'priority': 'MEDIUM'
        })
        
        # Check that the ticket was created
        self.assertEqual(Ticket.objects.count(), 1)
        ticket = Ticket.objects.first()
        self.assertEqual(ticket.title, 'Test Ticket')
        self.assertEqual(ticket.created_by, self.ir_user)
        self.assertEqual(ticket.status, 'NEW')
    
    def test_ticket_assignment_by_project_manager(self):
        """Test that a Project Manager can assign a ticket to a Support Engineer"""
        # Create a ticket
        ticket = Ticket.objects.create(
            title='Test Ticket',
            description='This is a test ticket',
            category='Hardware',
            priority='MEDIUM',
            status='NEW',
            created_by=self.ir_user
        )
        
        # Login as project manager
        self.client.login(username='pm_user', password='password123')
        
        # Assign the ticket
        response = self.client.post(
            reverse('assign_ticket', args=[ticket.id]),
            {
                'support_engineer': self.se_user.id,
                'notes': 'Handle ASAP',
            }
        )
        
        # Check that the ticket was assigned
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.se_user)
        self.assertEqual(ticket.status, 'IN_PROGRESS')
    
    def test_valid_status_transition(self):
        """Test valid status transition: OPEN -> IN_PROGRESS by Support Engineer"""
        # Create a ticket assigned to support engineer
        ticket = Ticket.objects.create(
            title='Test Ticket',
            description='This is a test ticket',
            category='Hardware',
            priority='MEDIUM',
            status='IN_PROGRESS',
            created_by=self.ir_user,
            assigned_to=self.se_user
        )
        
        # Login as support engineer
        self.client.login(username='se_user', password='password123')
        
        # Update the ticket status
        response = self.client.post(reverse('ticket_update', args=[ticket.id]), {
            'title': ticket.title,
            'status': 'RESOLVED',
            'priority': 'MEDIUM',
            'category': 'Hardware',
            'description': 'This is a test ticket'
        })
        
        # Check that the status was updated
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'RESOLVED')
    
    def test_invalid_status_transition(self):
        """Test invalid status transition: OPEN -> CLOSED by Support Engineer"""
        # Create a ticket assigned to support engineer
        ticket = Ticket.objects.create(
            title='Test Ticket',
            description='This is a test ticket',
            category='Hardware',
            priority='MEDIUM',
            status='IN_PROGRESS',
            created_by=self.ir_user,
            assigned_to=self.se_user
        )
        
        # Login as support engineer
        self.client.login(username='se_user', password='password123')
        
        # Try to update the ticket status to CLOSED (invalid transition)
        response = self.client.post(reverse('ticket_update', args=[ticket.id]), {
            'title': ticket.title,
            'status': 'CLOSED',
            'priority': 'MEDIUM',
            'category': 'Hardware',
            'description': 'This is a test ticket'
        })
        
        # Check that the status was not updated
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'IN_PROGRESS')
