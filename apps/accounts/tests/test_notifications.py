from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Notification

User = get_user_model()


class NotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="n@example.com", username="nuser", password="password"
        )
        self.other = User.objects.create_user(
            email="o@example.com", username="ouser", password="password"
        )
        Notification.objects.create(
            recipient=self.user, title="Welcome", message="Hi", type="support"
        )
        Notification.objects.create(
            recipient=self.other, title="Nope", message="Not yours", type="support"
        )

    def test_list_returns_only_own_notifications(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse("me-notifications"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "Welcome")

    def test_requires_auth(self):
        res = self.client.get(reverse("me-notifications"))
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_mark_all_read(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post(reverse("me-notifications-read"))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.user.notifications.filter(is_read=False).exists())
