from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.tests.factories import UserFactory
from apps.common.tests.helpers import MediaTestCase, make_image_file
from apps.subscriptions.tests.factories import SubscriptionFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class AvatarUploadTests(MediaTestCase):
    def test_basic_tier_blocked(self):
        user = UserFactory()
        response = self.client.put(
            "/api/auth/me/avatar/",
            {"avatar": make_image_file()},
            format="multipart",
            **auth_headers(user),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "avatar_upload_quota_exceeded")

    def test_silver_tier_succeeds_with_absolute_url(self):
        user = UserFactory()
        SubscriptionFactory(user=user, plan__tier="silver", status="active")
        response = self.client.put(
            "/api/auth/me/avatar/",
            {"avatar": make_image_file()},
            format="multipart",
            **auth_headers(user),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["avatar"].startswith("http://testserver/media/"))

    def test_delete_clears_avatar(self):
        user = UserFactory()
        SubscriptionFactory(user=user, plan__tier="gold", status="active")
        self.client.put(
            "/api/auth/me/avatar/",
            {"avatar": make_image_file()},
            format="multipart",
            **auth_headers(user),
        )
        response = self.client.delete("/api/auth/me/avatar/", **auth_headers(user))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.get(pk=user.pk).avatar)

    def test_login_response_carries_absolute_avatar_url(self):
        user = UserFactory(password="password123")
        SubscriptionFactory(user=user, plan__tier="silver", status="active")
        self.client.put(
            "/api/auth/me/avatar/",
            {"avatar": make_image_file()},
            format="multipart",
            **auth_headers(user),
        )
        response = self.client.post(
            "/api/auth/login/", {"email": user.email, "password": "password123"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["user"]["avatar"].startswith("http://testserver/media/"))
