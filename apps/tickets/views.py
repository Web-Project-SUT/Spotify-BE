from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsSupportOrAdmin

from . import services
from .models import Ticket
from .permissions import IsTicketParticipant
from .serializers import (
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
    TicketMessageCreateSerializer,
    TicketMessageSerializer,
    TicketStatusSerializer,
)


class TicketViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Ticket.objects.none()
        base = Ticket.objects.select_related("author").prefetch_related("messages__author")
        if self.action != "list" or self.request.user.role in ("support", "admin"):
            # Object-level permission (IsTicketParticipant) enforces
            # author-or-support access on individual tickets; a ticket owned
            # by someone else should 403, not be filtered out and read as a
            # 404.
            return base
        return base.filter(author=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return TicketListSerializer
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "partial_update":
            return TicketStatusSerializer
        return TicketDetailSerializer

    def get_permissions(self):
        if self.action == "partial_update":
            return [permissions.IsAuthenticated(), IsSupportOrAdmin()]
        if self.action == "retrieve":
            return [permissions.IsAuthenticated(), IsTicketParticipant()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.instance = services.create_ticket(
            author=self.request.user,
            subject=serializer.validated_data["subject"],
            body=serializer.validated_data["body"],
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = TicketDetailSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        output = TicketDetailSerializer(instance, context=self.get_serializer_context())
        return Response(output.data)


class TicketMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_ticket(self, request, ticket_id):
        ticket = get_object_or_404(Ticket, pk=ticket_id)
        if not IsTicketParticipant().has_object_permission(request, self, ticket):
            raise PermissionDenied
        return ticket

    def post(self, request, ticket_id):
        ticket = self.get_ticket(request, ticket_id)
        serializer = TicketMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = services.add_message(ticket, request.user, serializer.validated_data["body"])
        return Response(TicketMessageSerializer(message).data, status=status.HTTP_201_CREATED)
