from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.common.tests.helpers import MediaTestCase, make_image_file
from apps.playlists.tests.factories import PlaylistFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class PlaylistCoverTests(MediaTestCase):
    def test_owner_uploads_cover(self):
        owner = UserFactory()
        playlist = PlaylistFactory(owner=owner)
        response = self.client.put(
            f"/api/playlists/{playlist.id}/cover/",
            {"cover": make_image_file()},
            format="multipart",
            **auth_headers(owner),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["cover"].startswith("http://testserver/media/"))

    def test_non_owner_forbidden(self):
        owner = UserFactory()
        other = UserFactory()
        playlist = PlaylistFactory(owner=owner)
        response = self.client.put(
            f"/api/playlists/{playlist.id}/cover/",
            {"cover": make_image_file()},
            format="multipart",
            **auth_headers(other),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_clears_cover(self):
        owner = UserFactory()
        playlist = PlaylistFactory(owner=owner)
        self.client.put(
            f"/api/playlists/{playlist.id}/cover/",
            {"cover": make_image_file()},
            format="multipart",
            **auth_headers(owner),
        )
        response = self.client.delete(f"/api/playlists/{playlist.id}/cover/", **auth_headers(owner))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
