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
