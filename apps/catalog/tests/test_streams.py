from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.catalog.models import PlayEvent
from apps.catalog.tests.factories import TrackFactory


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
