from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.catalog.models import PlayEvent
from apps.catalog.tests.factories import TrackFactory
from apps.playlists.models import Playlist


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class PlaylistRecentTests(APITestCase):
    def test_recent_orders_by_most_recent_play(self):
        owner = UserFactory()
        older = Playlist.objects.create(owner=owner, title="Older")
        newer = Playlist.objects.create(owner=owner, title="Newer")
        track = TrackFactory()

        PlayEvent.objects.create(
            user=owner,
            track=track,
            playlist=older,
            played_at=timezone.now() - timezone.timedelta(hours=2),
        )
        PlayEvent.objects.create(user=owner, track=track, playlist=newer, played_at=timezone.now())

        response = self.client.get("/api/playlists/recent/", **auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p["id"] for p in response.data["results"]]
        self.assertEqual(ids.index(str(newer.id)), 0)

    def test_recent_returns_last_played_at_and_nulls_it_when_never_played(self):
        owner = UserFactory()
        played = Playlist.objects.create(owner=owner, title="Played")
        never = Playlist.objects.create(owner=owner, title="Never")
        PlayEvent.objects.create(user=owner, track=TrackFactory(), playlist=played)

        response = self.client.get("/api/playlists/recent/", **auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # .json() (not .data) so this pins the camelCased wire key the
        # frontend actually reads, not the pre-render snake_case dict.
        rows = {p["id"]: p["lastPlayedAt"] for p in response.json()["results"]}
        self.assertIsNotNone(rows[str(played.id)])
        self.assertIsNone(rows[str(never.id)])

    def test_playlist_list_also_carries_last_played_at(self):
        owner = UserFactory()
        playlist = Playlist.objects.create(owner=owner, title="Mine")
        PlayEvent.objects.create(user=owner, track=TrackFactory(), playlist=playlist)

        response = self.client.get("/api/playlists/", **auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.json()["results"][0]["lastPlayedAt"])
