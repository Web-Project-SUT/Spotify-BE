from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.catalog.tests.factories import TrackFactory
from apps.playlists.models import Playlist


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class PlaylistCrudTests(APITestCase):
    def test_create_rename_delete_round_trip(self):
        owner = UserFactory()
        headers = auth_headers(owner)

        create = self.client.post("/api/playlists/", {"title": "Chill"}, format="json", **headers)
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        playlist_id = create.data["id"]

        rename = self.client.patch(
            f"/api/playlists/{playlist_id}/",
            {"title": "Chill Vibes", "isPublic": True},
            format="json",
            **headers,
        )
        self.assertEqual(rename.status_code, status.HTTP_200_OK)
        self.assertEqual(rename.data["title"], "Chill Vibes")
        self.assertTrue(rename.data["is_public"])

        delete = self.client.delete(f"/api/playlists/{playlist_id}/", **headers)
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Playlist.objects.filter(id=playlist_id).exists())


class PlaylistQuotaTests(APITestCase):
    def test_basic_tier_seventh_playlist_returns_403(self):
        owner = UserFactory()
        headers = auth_headers(owner)
        for i in range(6):
            response = self.client.post(
                "/api/playlists/", {"title": f"Playlist {i}"}, format="json", **headers
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        seventh = self.client.post(
            "/api/playlists/", {"title": "One too many"}, format="json", **headers
        )
        self.assertEqual(seventh.status_code, status.HTTP_403_FORBIDDEN)


class PlaylistTracksTests(APITestCase):
    def test_add_and_reorder_preserves_order(self):
        owner = UserFactory()
        headers = auth_headers(owner)
        playlist = Playlist.objects.create(owner=owner, title="Mix")
        track_a = TrackFactory()
        track_b = TrackFactory()

        self.client.post(
            f"/api/playlists/{playlist.id}/tracks/",
            {"track": str(track_a.id)},
            format="json",
            **headers,
        )
        self.client.post(
            f"/api/playlists/{playlist.id}/tracks/",
            {"track": str(track_b.id)},
            format="json",
            **headers,
        )

        reorder = self.client.put(
            f"/api/playlists/{playlist.id}/tracks/",
            {"order": [str(track_b.id), str(track_a.id)]},
            format="json",
            **headers,
        )
        self.assertEqual(reorder.status_code, status.HTTP_200_OK)
        track_ids = [t["id"] for t in reorder.data["tracks"]]
        self.assertEqual(track_ids, [str(track_b.id), str(track_a.id)])


class PlaylistListMembershipTests(APITestCase):
    def test_list_returns_track_ids_for_membership_checks(self):
        owner = UserFactory()
        headers = auth_headers(owner)
        playlist = Playlist.objects.create(owner=owner, title="Mix")
        track = TrackFactory()
        self.client.post(
            f"/api/playlists/{playlist.id}/tracks/",
            {"track": str(track.id)},
            format="json",
            **headers,
        )

        response = self.client.get("/api/playlists/", **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()["results"][0]
        self.assertEqual(row["trackIds"], [str(track.id)])


class PlaylistPrivacyTests(APITestCase):
    def test_other_user_cannot_read_private_playlist(self):
        owner = UserFactory()
        other = UserFactory()
        playlist = Playlist.objects.create(owner=owner, title="Secret", is_public=False)

        response = self.client.get(f"/api/playlists/{playlist.id}/", **auth_headers(other))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
