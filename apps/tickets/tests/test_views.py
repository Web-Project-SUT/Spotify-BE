from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Notification
from apps.accounts.tests.factories import UserFactory
from apps.tickets.models import Ticket
from apps.tickets.tests.factories import TicketFactory, TicketMessageFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class TicketCreateTests(APITestCase):
    def test_listener_files_a_ticket_and_support_is_notified(self):
        listener = UserFactory()
        support = UserFactory(role="support")

        response = self.client.post(
            "/api/tickets/",
            {"subject": "Can't play a track", "body": "The player hangs on load."},
            format="json",
            **auth_headers(listener),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subject"], "Can't play a track")
        self.assertEqual(response.data["status"], "open")
        self.assertEqual(len(response.data["messages"]), 1)
        self.assertEqual(response.data["messages"][0]["body"], "The player hangs on load.")

        self.assertTrue(
            Notification.objects.filter(
                recipient=support, type="support", title="New support ticket"
            ).exists()
        )


class TicketListScopingTests(APITestCase):
    def test_listener_sees_only_their_own_tickets(self):
        mine = TicketFactory()
        TicketFactory()  # someone else's

        response = self.client.get("/api/tickets/", **auth_headers(mine.author))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {str(mine.id)})

    def test_support_sees_every_ticket(self):
        support = UserFactory(role="support")
        first = TicketFactory()
        second = TicketFactory()

        response = self.client.get("/api/tickets/", **auth_headers(support))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {str(first.id), str(second.id)})


class TicketRetrieveTests(APITestCase):
    def test_other_listener_cannot_read_someone_elses_ticket(self):
        ticket = TicketFactory()
        other = UserFactory()

        response = self.client.get(f"/api/tickets/{ticket.id}/", **auth_headers(other))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_can_read_any_ticket(self):
        ticket = TicketFactory()
        support = UserFactory(role="support")

        response = self.client.get(f"/api/tickets/{ticket.id}/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TicketReplyTests(APITestCase):
    def test_support_reply_marks_answered_and_notifies_author(self):
        ticket = TicketFactory(status=Ticket.Status.OPEN)
        TicketMessageFactory(ticket=ticket, author=ticket.author)
        support = UserFactory(role="support")

        response = self.client.post(
            f"/api/tickets/{ticket.id}/messages/",
            {"body": "Try clearing your cache."},
            format="json",
            **auth_headers(support),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.ANSWERED)
        self.assertTrue(
            Notification.objects.filter(
                recipient=ticket.author,
                type="support",
                title="Support replied to your ticket",
            ).exists()
        )

    def test_a_reply_reopens_a_closed_ticket(self):
        ticket = TicketFactory(status=Ticket.Status.CLOSED)

        response = self.client.post(
            f"/api/tickets/{ticket.id}/messages/",
            {"body": "Actually, still broken."},
            format="json",
            **auth_headers(ticket.author),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.OPEN)

    def test_stranger_cannot_reply_to_someone_elses_ticket(self):
        ticket = TicketFactory()
        other = UserFactory()

        response = self.client.post(
            f"/api/tickets/{ticket.id}/messages/",
            {"body": "Sneaky reply."},
            format="json",
            **auth_headers(other),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TicketStatusTests(APITestCase):
    def test_support_can_close_a_ticket(self):
        ticket = TicketFactory(status=Ticket.Status.ANSWERED)
        support = UserFactory(role="support")

        response = self.client.patch(
            f"/api/tickets/{ticket.id}/",
            {"status": "closed"},
            format="json",
            **auth_headers(support),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.CLOSED)

    def test_listener_cannot_close_their_own_ticket(self):
        ticket = TicketFactory()

        response = self.client.patch(
            f"/api/tickets/{ticket.id}/",
            {"status": "closed"},
            format="json",
            **auth_headers(ticket.author),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_cannot_reopen_via_patch(self):
        ticket = TicketFactory(status=Ticket.Status.CLOSED)
        support = UserFactory(role="support")

        response = self.client.patch(
            f"/api/tickets/{ticket.id}/",
            {"status": "open"},
            format="json",
            **auth_headers(support),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_delete_endpoint(self):
        ticket = TicketFactory()
        support = UserFactory(role="support")

        response = self.client.delete(f"/api/tickets/{ticket.id}/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
