import json
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Ticket, Comment, Attachment
from .serializers import (
    TicketSerializer, TicketUpdateSerializer, TicketAssignSerializer,
    CommentSerializer, AttachmentSerializer
)
from .rbac import (
    get_user_role, can_view_ticket, can_update_ticket, 
    can_assign_ticket, can_change_status
)

class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        user_role = get_user_role(user)
        
        if user_role == 'PROJECT_MANAGER':
            return Ticket.objects.all().order_by('-created_at')
        elif user_role == 'SUPPORT_ENGINEER':
            return Ticket.objects.filter(assigned_to=user).order_by('-updated_at')
        elif user_role == 'ISSUE_REPORTER':
            return Ticket.objects.filter(created_by=user).order_by('-created_at')
        return Ticket.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'update' or self.action == 'partial_update':
            return TicketUpdateSerializer
        elif self.action == 'assign':
            return TicketAssignSerializer
        return TicketSerializer
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_view_ticket(request.user, instance):
            return Response(
                {"detail": "You don't have permission to view this ticket."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_update_ticket(request.user, instance):
            return Response(
                {"detail": "You don't have permission to update this ticket."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check status transition if status is being changed
        if 'status' in request.data:
            new_status = request.data['status']
            if instance.status != new_status and not can_change_status(request.user, instance, new_status):
                return Response(
                    {"detail": "You don't have permission to change the status to this value."},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        return super().update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        
        if not can_assign_ticket(request.user):
            return Response(
                {"detail": "You don't have permission to assign tickets."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = TicketAssignSerializer(ticket, data=request.data)
        if serializer.is_valid():
            ticket = serializer.save()
            ticket.assigned_at = timezone.now()
            ticket.save()
            
            # Create audit log entry
            from .models import AuditLog
            AuditLog.objects.create(
                ticket=ticket,
                action="Ticket assigned via API",
                performed_by=request.user,
                meta=json.dumps({
                    "assigned_to": ticket.assigned_to.username if ticket.assigned_to else None
                })
            )
            
            # Send email notification
            # (This would be implemented in a production environment)
            
            return Response(TicketSerializer(ticket).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Comment.objects.none()  # Base queryset is empty, we'll override get/list methods
    
    def create(self, request, *args, **kwargs):
        ticket_id = request.data.get('ticket_id')
        if not ticket_id:
            return Response(
                {"detail": "Ticket ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket = get_object_or_404(Ticket, pk=ticket_id)
        
        if not can_view_ticket(request.user, ticket):
            return Response(
                {"detail": "You don't have permission to comment on this ticket."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'ticket_id': ticket_id}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Create audit log entry
        from .models import AuditLog
        AuditLog.objects.create(
            ticket=ticket,
            action="Comment added via API",
            performed_by=request.user
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class AttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = AttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Attachment.objects.none()  # Base queryset is empty, we'll override get/list methods
    
    def create(self, request, *args, **kwargs):
        ticket_id = request.data.get('ticket_id')
        if not ticket_id:
            return Response(
                {"detail": "Ticket ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket = get_object_or_404(Ticket, pk=ticket_id)
        
        if not can_view_ticket(request.user, ticket):
            return Response(
                {"detail": "You don't have permission to add attachments to this ticket."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'ticket_id': ticket_id}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Create audit log entry
        from .models import AuditLog
        AuditLog.objects.create(
            ticket=ticket,
            action="Attachment added via API",
            performed_by=request.user
        )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)