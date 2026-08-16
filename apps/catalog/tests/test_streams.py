from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.catalog.models import PlayEvent
from apps.catalog.tests.factories import PlayEventFactory, TrackFactory
from apps.playlists.tests.factories import PlaylistFactory
from apps.subscriptions.tests.factories import SubscriptionFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class StreamCreateTests(APITestCase):
    def test_post_stream_creates_play_event_and_bumps_play_count(self):
        listener = UserFactory()
        track = TrackFactory()

        response = self.client.post(
            "/api/streams/",
            {"track": str(track.id)},
            format="json",
            **auth_headers(listener),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlayEvent.objects.filter(user=listener, track=track).count(), 1)
        track.refresh_from_db()
        self.assertEqual(track.play_count, 1)

    def test_stream_records_the_playlist_it_was_played_from(self):
        listener = UserFactory()
        track = TrackFactory()
        playlist = PlaylistFactory(owner=listener)

        response = self.client.post(
            "/api/streams/",
            {"track": str(track.id), "playlist": str(playlist.id)},
            format="json",
            **auth_headers(listener),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlayEvent.objects.get(user=listener, track=track).playlist, playlist)


class DailyStreamQuotaTests(APITestCase):
    """The 60/day basic-tier cap the spec headlines; enforced at the only
    request-driven PlayEvent creation point."""

    def test_basic_listener_is_blocked_after_the_daily_limit(self):
        listener = UserFactory()
        track = TrackFactory()
        PlayEventFactory.create_batch(60, user=listener, track=track)

        response = self.client.post(
            "/api/streams/",
            {"track": str(track.id)},
            format="json",
            **auth_headers(listener),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "daily_stream_quota_exceeded")
        self.assertEqual(PlayEvent.objects.filter(user=listener).count(), 60)

    def test_silver_listener_is_unlimited(self):
        listener = UserFactory()
        SubscriptionFactory(user=listener, plan__tier="silver", status="active")
        track = TrackFactory()
        PlayEventFactory.create_batch(60, user=listener, track=track)

        response = self.client.post(
            "/api/streams/",
            {"track": str(track.id)},
            format="json",
            **auth_headers(listener),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PlayEvent.objects.filter(user=listener).count(), 61)
