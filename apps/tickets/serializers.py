from rest_framework import serializers

from apps.accounts.models import User

from .models import Ticket, TicketMessage


class TicketAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "display_name", "role"]


class TicketMessageSerializer(serializers.ModelSerializer):
    author = TicketAuthorSerializer(read_only=True)

    class Meta:
        model = TicketMessage
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = fields


class TicketMessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketMessage
        fields = ["body"]


class TicketListSerializer(serializers.ModelSerializer):
    author = TicketAuthorSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ["id", "author", "subject", "status", "created_at", "updated_at"]
        read_only_fields = fields


class TicketDetailSerializer(serializers.ModelSerializer):
    author = TicketAuthorSerializer(read_only=True)
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = ["id", "author", "subject", "status", "created_at", "updated_at", "messages"]
        read_only_fields = fields


class TicketCreateSerializer(serializers.ModelSerializer):
    body = serializers.CharField(write_only=True)

    class Meta:
        model = Ticket
        fields = ["subject", "body"]


class TicketStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["status"]

    def validate_status(self, value):
        # The only support-initiated transition is closing a ticket; a reply
        # already flips open -> answered (services.add_message), and nothing
        # should be able to force a ticket back to "open" by hand.
        if value != Ticket.Status.CLOSED:
            raise serializers.ValidationError("Tickets can only be closed through this endpoint.")
        return value
