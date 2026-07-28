from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.tests.factories import TrackFactory
from apps.common.media import replace_files
from apps.common.tests.helpers import MediaTestCase, make_audio_file
from apps.subscriptions.tests.factories import SubscriptionFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class TrackDownloadTests(MediaTestCase):
    def _track_with_audio(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        audio = make_audio_file("hi.mp3", payload=b"ID3" + bytes(2000))
        replace_files(track, {"audio_high": audio})
        track.refresh_from_db()
        return track

    def test_basic_tier_forbidden(self):
        track = self._track_with_audio()
        listener = UserFactory()
        response = self.client.get(f"/api/tracks/{track.id}/download/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_silver_tier_gets_attachment(self):
        track = self._track_with_audio()
        listener = UserFactory()
        SubscriptionFactory(user=listener, plan__tier="silver", status="active")
        response = self.client.get(f"/api/tracks/{track.id}/download/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_range_request_returns_partial_content(self):
        track = self._track_with_audio()
        listener = UserFactory()
        SubscriptionFactory(user=listener, plan__tier="gold", status="active")
        response = self.client.get(
            f"/api/tracks/{track.id}/download/",
            HTTP_RANGE="bytes=0-99",
            **auth_headers(listener),
        )
        self.assertEqual(response.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertTrue(response["Content-Range"].startswith("bytes 0-99/"))
