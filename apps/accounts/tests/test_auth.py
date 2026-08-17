from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AccountStatus, Notification, Role, User
from apps.accounts.tests.factories import UserFactory
from apps.subscriptions.models import Subscription
from apps.subscriptions.tests.factories import SubscriptionFactory


class RegisterListenerTests(APITestCase):
    def test_register_auto_logs_in_and_assigns_unique_username(self):
        response = self.client.post(
            "/api/auth/register/listener/",
            {
                "email": "listener@example.com",
                "password": "supersecret1",
                "displayName": "Ava Listener",
                "acceptedPolicy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        user = User.objects.get(email="listener@example.com")
        self.assertTrue(user.username)
        self.assertEqual(user.role, Role.LISTENER)

    def test_duplicate_email_returns_400(self):
        UserFactory(email="dup@example.com")
        response = self.client.post(
            "/api/auth/register/listener/",
            {
                "email": "dup@example.com",
                "password": "supersecret1",
                "displayName": "Dup",
                "acceptedPolicy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RegisterArtistTests(APITestCase):
    def test_register_returns_no_tokens_pending_status_and_notifies_staff(self):
        support = UserFactory(role=Role.SUPPORT)
        admin = UserFactory(role=Role.ADMIN)

        response = self.client.post(
            "/api/auth/register/artist/",
            {
                "email": "artist@example.com",
                "password": "supersecret1",
                "stageName": "Nova Ray",
                "portfolio": "https://example.com/nova",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

        user = User.objects.get(email="artist@example.com")
        self.assertEqual(user.status, AccountStatus.PENDING)

        self.assertTrue(Notification.objects.filter(recipient=support).exists())
        self.assertTrue(Notification.objects.filter(recipient=admin).exists())


class LoginTests(APITestCase):
    def test_login_succeeds_with_correct_password(self):
        UserFactory(email="user@example.com", password="correct-pass")
        response = self.client.post(
            "/api/auth/login/",
            {"email": "user@example.com", "password": "correct-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("user", response.data)

    def test_login_fails_with_wrong_password(self):
        UserFactory(email="user2@example.com", password="correct-pass")
        response = self.client.post(
            "/api/auth/login/",
            {"email": "user2@example.com", "password": "wrong-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeTests(APITestCase):
    def test_me_requires_authentication(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_exposes_the_active_subscription_period_and_expiry(self):
        """/upgrade needs the expiry and period to offer a renewal (C-14)."""
        user = UserFactory(email="subscriber@example.com")
        expires = timezone.now() + timedelta(days=90)
        SubscriptionFactory(
            user=user,
            period_months=3,
            expires_at=expires,
            status=Subscription.Status.ACTIVE,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Read the rendered payload: the frontend consumes camelCase keys.
        subscription = response.json()["subscription"]
        self.assertEqual(subscription["tier"], "silver")
        self.assertEqual(subscription["periodMonths"], 3)
        self.assertEqual(subscription["status"], Subscription.Status.ACTIVE)
        self.assertEqual(subscription["expiresAt"][:19], expires.isoformat()[:19])

    def test_me_reports_no_subscription_for_a_basic_listener(self):
        user = UserFactory(email="freeloader@example.com")
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/auth/me/")

        self.assertIsNone(response.json()["subscription"])
        self.assertEqual(response.json()["tier"], "basic")

    def test_me_ignores_a_lapsed_subscription_like_tier_does(self):
        user = UserFactory(email="lapsed@example.com")
        SubscriptionFactory(
            user=user,
            expires_at=timezone.now() - timedelta(days=1),
            status=Subscription.Status.ACTIVE,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/auth/me/")

        self.assertIsNone(response.json()["subscription"])
        self.assertEqual(response.json()["tier"], "basic")


class RefreshTests(APITestCase):
    def test_refresh_rotates_and_blacklists_old_token(self):
        user = UserFactory(email="refresh@example.com", password="correct-pass")
        login = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "correct-pass"},
            format="json",
        )
        old_refresh = login.data["refresh"]

        first = self.client.post("/api/auth/refresh/", {"refresh": old_refresh}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post("/api/auth/refresh/", {"refresh": old_refresh}, format="json")
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(APITestCase):
    def test_request_returns_204_for_unknown_email_without_enumeration(self):
        response = self.client.post(
            "/api/auth/password-reset/",
            {"email": "nobody@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
