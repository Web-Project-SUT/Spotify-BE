from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class Ticket(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ANSWERED = "answered", "Answered"
        CLOSED = "closed", "Closed"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets"
    )
    subject = models.CharField(max_length=140)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["author", "-created_at"])]

    def __str__(self):
        return self.subject


class TicketMessage(UUIDModel, TimeStampedModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_messages"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket_id}#{self.pk}"
