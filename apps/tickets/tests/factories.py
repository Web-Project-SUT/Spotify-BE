import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.tickets.models import Ticket, TicketMessage


class TicketFactory(DjangoModelFactory):
    class Meta:
        model = Ticket

    author = factory.SubFactory(UserFactory)
    subject = factory.Sequence(lambda n: f"Ticket subject {n}")


class TicketMessageFactory(DjangoModelFactory):
    class Meta:
        model = TicketMessage

    ticket = factory.SubFactory(TicketFactory)
    author = factory.SelfAttribute("ticket.author")
    body = factory.Sequence(lambda n: f"Message body {n}")
