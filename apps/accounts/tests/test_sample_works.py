from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus, Role, SampleWork
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.common.tests.helpers import MediaTestCase, make_audio_file


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class SampleWorkUploadTests(MediaTestCase):
    def test_pending_artist_can_upload(self):
        artist = ArtistUserFactory(status=AccountStatus.PENDING)
        response = self.client.post(
            "/api/artists/me/sample-works/",
            {"title": "Demo", "file": make_audio_file()},
            format="multipart",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SampleWork.objects.filter(artist__user=artist).count(), 1)

    def test_listener_cannot_upload(self):
        listener = UserFactory()
        response = self.client.post(
            "/api/artists/me/sample-works/",
            {"title": "Demo", "file": make_audio_file()},
            format="multipart",
            **auth_headers(listener),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_can_list_another_artists_sample_works(self):
        artist = ArtistUserFactory()
        self.client.post(
            "/api/artists/me/sample-works/",
            {"title": "Demo", "file": make_audio_file()},
            format="multipart",
            **auth_headers(artist),
        )
        support = UserFactory(role=Role.SUPPORT)
        response = self.client.get(
            f"/api/artists/{artist.id}/sample-works/", **auth_headers(support)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_listener_cannot_list_another_artists_sample_works(self):
        artist = ArtistUserFactory()
        listener = UserFactory()
        response = self.client.get(
            f"/api/artists/{artist.id}/sample-works/", **auth_headers(listener)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
