from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus
from apps.accounts.tests.factories import ArtistUserFactory
from apps.catalog.tests.factories import AlbumFactory, TrackFactory
from apps.common.tests.helpers import MediaTestCase, make_audio_file, make_image_file


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class TrackCoverTests(MediaTestCase):
    def test_owner_uploads_cover(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        response = self.client.put(
            f"/api/tracks/{track.id}/cover/",
            {"cover": make_image_file()},
            format="multipart",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["cover"].startswith("http://testserver/media/"))

    def test_non_owner_forbidden(self):
        artist = ArtistUserFactory()
        other = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        response = self.client.put(
            f"/api/tracks/{track.id}/cover/",
            {"cover": make_image_file()},
            format="multipart",
            **auth_headers(other),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AlbumCoverTests(MediaTestCase):
    def test_owner_uploads_cover(self):
        artist = ArtistUserFactory()
        album = AlbumFactory(artist=artist)
        response = self.client.put(
            f"/api/albums/{album.id}/cover/",
            {"cover": make_image_file()},
            format="multipart",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["cover"].startswith("http://testserver/media/"))


class TrackAudioTests(MediaTestCase):
    def test_owner_uploads_both_variants(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        response = self.client.put(
            f"/api/tracks/{track.id}/audio/",
            {"audioHigh": make_audio_file("hi.mp3"), "audioLow": make_audio_file("lo.mp3")},
            format="multipart",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["audio_high"].startswith("http://testserver/media/"))
        self.assertTrue(response.data["audio_low"].startswith("http://testserver/media/"))

    def test_missing_audio_low_returns_400(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        response = self.client.put(
            f"/api/tracks/{track.id}/audio/",
            {"audioHigh": make_audio_file("hi.mp3")},
            format="multipart",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("audio_low", response.data["fields"])

    def test_non_owner_forbidden(self):
        artist = ArtistUserFactory()
        other = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        response = self.client.put(
            f"/api/tracks/{track.id}/audio/",
            {"audioHigh": make_audio_file("hi.mp3"), "audioLow": make_audio_file("lo.mp3")},
            format="multipart",
            **auth_headers(other),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unapproved_artist_blocked(self):
        artist = ArtistUserFactory(status=AccountStatus.PENDING)
        track = TrackFactory(artist=artist)
        response = self.client.put(
            f"/api/tracks/{track.id}/audio/",
            {"audioHigh": make_audio_file("hi.mp3"), "audioLow": make_audio_file("lo.mp3")},
            format="multipart",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
