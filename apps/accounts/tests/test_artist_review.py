from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus, ArtistProfile, Notification, Role
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class PendingArtistListTests(APITestCase):
    def test_support_sees_only_pending_artists(self):
        support = UserFactory(role=Role.SUPPORT)
        pending = ArtistUserFactory(status=AccountStatus.PENDING)
        ArtistUserFactory(status=AccountStatus.ACTIVE)

        response = self.client.get("/api/artists/pending/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {str(pending.id)})

    def test_listener_cannot_view_the_queue(self):
        listener = UserFactory()
        response = self.client.get("/api/artists/pending/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ArtistApproveTests(APITestCase):
    def test_support_approves_a_pending_artist(self):
        support = UserFactory(role=Role.SUPPORT)
        artist = ArtistUserFactory(status=AccountStatus.PENDING)

        response = self.client.post(f"/api/artists/{artist.id}/approve/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        artist.refresh_from_db()
        self.assertEqual(artist.status, AccountStatus.ACTIVE)
        profile = ArtistProfile.objects.get(user=artist)
        self.assertIsNotNone(profile.verified_at)
        self.assertEqual(profile.reviewed_by, support)
        self.assertIsNotNone(profile.reviewed_at)
        self.assertTrue(
            Notification.objects.filter(
                recipient=artist, type="approval", title="Artist account approved"
            ).exists()
        )

    def test_cannot_approve_an_already_active_artist(self):
        support = UserFactory(role=Role.SUPPORT)
        artist = ArtistUserFactory(status=AccountStatus.ACTIVE)

        response = self.client.post(f"/api/artists/{artist.id}/approve/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_listener_cannot_approve(self):
        listener = UserFactory()
        artist = ArtistUserFactory(status=AccountStatus.PENDING)

        response = self.client.post(f"/api/artists/{artist.id}/approve/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ArtistRejectTests(APITestCase):
    def test_support_rejects_with_a_reason(self):
        support = UserFactory(role=Role.SUPPORT)
        artist = ArtistUserFactory(status=AccountStatus.PENDING)

        response = self.client.post(
            f"/api/artists/{artist.id}/reject/",
            {"reason": "Samples did not meet quality bar"},
            format="json",
            **auth_headers(support),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        artist.refresh_from_db()
        self.assertEqual(artist.status, AccountStatus.REJECTED)
        profile = ArtistProfile.objects.get(user=artist)
        self.assertEqual(profile.rejection_reason, "Samples did not meet quality bar")
        self.assertEqual(profile.reviewed_by, support)

        notification = Notification.objects.get(recipient=artist, type="approval")
        self.assertIn("Samples did not meet quality bar", notification.message)

    def test_reject_requires_a_reason(self):
        support = UserFactory(role=Role.SUPPORT)
        artist = ArtistUserFactory(status=AccountStatus.PENDING)

        response = self.client.post(
            f"/api/artists/{artist.id}/reject/", {}, format="json", **auth_headers(support)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        artist.refresh_from_db()
        self.assertEqual(artist.status, AccountStatus.PENDING)
