from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.tests.factories import TrackFactory
from apps.subscriptions.tests.factories import SubscriptionFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class TrackStatsVisibilityTests(APITestCase):
    """D-1: play/listener counts are gold-only server-side."""

    def _row(self, response, track_id):
        return next(r for r in response.json()["results"] if r["id"] == str(track_id))

    def test_basic_listener_gets_null_stats(self):
        track = TrackFactory(play_count=5, unique_listener_count=3)
        basic = UserFactory()
        row = self._row(self.client.get("/api/tracks/", **auth_headers(basic)), track.id)
        self.assertIsNone(row["playCount"])
        self.assertIsNone(row["uniqueListenerCount"])

    def test_gold_listener_sees_stats(self):
        track = TrackFactory(play_count=5, unique_listener_count=3)
        gold = UserFactory()
        SubscriptionFactory(user=gold, plan__tier="gold", status="active")
        row = self._row(self.client.get("/api/tracks/", **auth_headers(gold)), track.id)
        self.assertEqual(row["playCount"], 5)
        self.assertEqual(row["uniqueListenerCount"], 3)

    def test_artist_sees_own_track_stats_even_without_gold(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist, play_count=7, unique_listener_count=4)
        row = self._row(self.client.get("/api/tracks/", **auth_headers(artist)), track.id)
        self.assertEqual(row["playCount"], 7)

    def test_staff_sees_stats(self):
        track = TrackFactory(play_count=9, unique_listener_count=6)
        staff = UserFactory(is_staff=True)
        row = self._row(self.client.get("/api/tracks/", **auth_headers(staff)), track.id)
        self.assertEqual(row["playCount"], 9)
