from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AccountStatus, Notification, Role, User
from apps.accounts.tests.factories import UserFactory


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
