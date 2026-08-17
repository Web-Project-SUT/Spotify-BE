from apps.accounts.models import Role, User
from apps.accounts.services import notify

from .models import Ticket, TicketMessage


def create_ticket(*, author, subject, body):
    ticket = Ticket.objects.create(author=author, subject=subject)
    TicketMessage.objects.create(ticket=ticket, author=author, body=body)
    recipients = User.objects.filter(role__in=[Role.SUPPORT, Role.ADMIN])
    notify(
        recipients,
        type="support",
        title="New support ticket",
        message=f"{author.display_name or author.email} submitted: {subject}",
    )
    return ticket


def add_message(ticket, author, body):
    message = TicketMessage.objects.create(ticket=ticket, author=author, body=body)
    if author.role in (Role.SUPPORT, Role.ADMIN):
        ticket.status = Ticket.Status.ANSWERED
        ticket.save(update_fields=["status", "updated_at"])
        if ticket.author_id != author.id:
            notify(
                [ticket.author],
                type="support",
                title="Support replied to your ticket",
                message=f"Re: {ticket.subject}",
            )
    elif ticket.status == Ticket.Status.CLOSED:
        ticket.status = Ticket.Status.OPEN
        ticket.save(update_fields=["status", "updated_at"])
    return message
