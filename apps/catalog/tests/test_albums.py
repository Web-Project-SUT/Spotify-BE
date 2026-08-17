from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.models import Album, Track
from apps.catalog.tests.factories import AlbumFactory, TrackFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class AlbumCreateTests(APITestCase):
    def test_approved_artist_creates_an_album(self):
        artist = ArtistUserFactory()
        response = self.client.post(
            "/api/albums/",
            {"title": "Skyline Echoes", "releaseYear": 2026},
            format="json",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        album = Album.objects.get(id=response.data["id"])
        self.assertEqual(album.artist_id, artist.id)
        self.assertEqual(album.title, "Skyline Echoes")
        self.assertEqual(album.release_year, 2026)

    def test_listener_cannot_create_an_album(self):
        listener = UserFactory()
        response = self.client.post(
            "/api/albums/",
            {"title": "Not Mine"},
            format="json",
            **auth_headers(listener),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unapproved_artist_cannot_create_an_album(self):
        artist = ArtistUserFactory(status=AccountStatus.PENDING)
        response = self.client.post(
            "/api/albums/",
            {"title": "Too Soon"},
            format="json",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AlbumOwnershipTests(APITestCase):
    def test_owner_renames_their_album(self):
        artist = ArtistUserFactory()
        album = AlbumFactory(artist=artist, title="Old Title")
        response = self.client.patch(
            f"/api/albums/{album.id}/",
            {"title": "New Title"},
            format="json",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        album.refresh_from_db()
        self.assertEqual(album.title, "New Title")

    def test_non_owner_cannot_patch_album(self):
        album = AlbumFactory(artist=ArtistUserFactory())
        response = self.client.patch(
            f"/api/albums/{album.id}/",
            {"title": "Hijacked"},
            format="json",
            **auth_headers(ArtistUserFactory()),
        )
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_owner_deletes_their_album(self):
        artist = ArtistUserFactory()
        album = AlbumFactory(artist=artist)
        response = self.client.delete(f"/api/albums/{album.id}/", **auth_headers(artist))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Album.objects.filter(id=album.id).exists())


class AlbumFilterTests(APITestCase):
    """The artist panel asks for its own albums rather than paging the catalog."""

    def test_filter_by_artist_returns_only_that_artists_albums(self):
        mine = ArtistUserFactory()
        theirs = ArtistUserFactory()
        AlbumFactory(artist=mine)
        AlbumFactory(artist=mine)
        AlbumFactory(artist=theirs)

        response = self.client.get(f"/api/albums/?artist={mine.id}", **auth_headers(mine))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertTrue(all(row["artist"] == str(mine.id) for row in response.data["results"]))


class TrackAlbumAssignmentTests(APITestCase):
    def test_owner_moves_a_track_into_their_album(self):
        artist = ArtistUserFactory()
        album = AlbumFactory(artist=artist)
        track = TrackFactory(artist=artist)
        response = self.client.patch(
            f"/api/tracks/{track.id}/",
            {"album": str(album.id), "releaseType": "album_track"},
            format="json",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        track.refresh_from_db()
        self.assertEqual(track.album_id, album.id)
        self.assertEqual(track.release_type, "album_track")

    def test_track_cannot_be_assigned_to_someone_elses_album(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        response = self.client.patch(
            f"/api/tracks/{track.id}/",
            {"album": str(AlbumFactory(artist=ArtistUserFactory()).id)},
            format="json",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("album", response.data["fields"])

    def test_owner_edits_track_metadata(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist, title="Draft", genre="pop")
        response = self.client.patch(
            f"/api/tracks/{track.id}/",
            {
                "title": "Released",
                "genre": "synth-pop",
                "lyrics": "city lights",
                "collaborators": ["Echo Drift"],
            },
            format="json",
            **auth_headers(artist),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["collaborators"], ["Echo Drift"])
        track = Track.objects.get(id=track.id)
        self.assertEqual(track.title, "Released")
        self.assertEqual(track.genre, "synth-pop")
        self.assertEqual(track.lyrics, "city lights")

    def test_track_list_exposes_collaborators(self):
        """The edit form prefills from the read endpoint, so it must be there."""
        artist = ArtistUserFactory()
        TrackFactory(artist=artist, collaborators=["Nova Ray"])
        response = self.client.get("/api/tracks/", **auth_headers(UserFactory()))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["collaborators"], ["Nova Ray"])
