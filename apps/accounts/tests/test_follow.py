from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Follow
from apps.accounts.tests.factories import UserFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class FollowTests(APITestCase):
    def test_follow_creates_relation(self):
        follower = UserFactory()
        target = UserFactory()

        response = self.client.post(f"/api/users/{target.id}/follow/", **auth_headers(follower))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Follow.objects.filter(follower=follower, following=target).exists())

    def test_unfollow_deletes_relation(self):
        follower = UserFactory()
        target = UserFactory()
        Follow.objects.create(follower=follower, following=target)

        response = self.client.delete(f"/api/users/{target.id}/follow/", **auth_headers(follower))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Follow.objects.filter(follower=follower, following=target).exists())

    def test_cannot_follow_self(self):
        user = UserFactory()
        response = self.client.post(f"/api/users/{user.id}/follow/", **auth_headers(user))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
