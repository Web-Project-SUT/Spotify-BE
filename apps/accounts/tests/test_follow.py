from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Follow
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory


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


class ProfileFollowFieldsTests(APITestCase):
    """The social numbers a profile page renders come from the API, not the client."""

    def test_user_detail_returns_follow_counts(self):
        target = UserFactory()
        followers = [UserFactory() for _ in range(3)]
        for follower in followers:
            Follow.objects.create(follower=follower, following=target)
        Follow.objects.create(follower=target, following=UserFactory())

        response = self.client.get(f"/api/users/{target.id}/", **auth_headers(followers[0]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["followerCount"], 3)
        self.assertEqual(response.json()["followingCount"], 1)

    def test_is_following_reflects_the_viewer(self):
        target = UserFactory()
        follower = UserFactory()
        stranger = UserFactory()
        Follow.objects.create(follower=follower, following=target)

        followed = self.client.get(f"/api/users/{target.id}/", **auth_headers(follower))
        self.assertTrue(followed.json()["isFollowing"])

        not_followed = self.client.get(f"/api/users/{target.id}/", **auth_headers(stranger))
        self.assertFalse(not_followed.json()["isFollowing"])

    def test_is_following_is_false_for_self(self):
        user = UserFactory()
        response = self.client.get(f"/api/users/{user.id}/", **auth_headers(user))
        self.assertFalse(response.json()["isFollowing"])

    def test_artist_detail_returns_follow_state(self):
        artist = ArtistUserFactory()
        follower = UserFactory()
        Follow.objects.create(follower=follower, following=artist)

        response = self.client.get(f"/api/artists/{artist.id}/", **auth_headers(follower))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["followerCount"], 1)
        self.assertTrue(response.json()["isFollowing"])
