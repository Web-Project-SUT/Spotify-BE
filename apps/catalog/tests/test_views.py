from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ArtistProfile
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.tests.factories import AlbumFactory, TrackFactory
from apps.subscriptions.tests.factories import SubscriptionFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class TrackListPermissionTests(APITestCase):
    def test_anonymous_list_returns_401(self):
        response = self.client.get("/api/tracks/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_artist_post_returns_403(self):
        listener = UserFactory()
        response = self.client.post(
            "/api/tracks/",
            {"title": "New Track", "genre": "pop"},
            format="json",
            **auth_headers(listener),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TrackOwnershipTests(APITestCase):
    def test_non_owner_cannot_patch_track(self):
        owner = ArtistUserFactory()
        other = ArtistUserFactory()
        track = TrackFactory(artist=owner)
        response = self.client.patch(
            f"/api/tracks/{track.id}/",
            {"title": "Hacked"},
            format="json",
            **auth_headers(other),
        )
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))


class AlbumDetailTests(APITestCase):
    def test_album_detail_returns_only_its_own_tracks(self):
        artist = ArtistUserFactory()
        other_artist = ArtistUserFactory()
        album = AlbumFactory(artist=artist)
        own_track_a = TrackFactory(artist=artist, album=album)
        own_track_b = TrackFactory(artist=artist, album=album)
        TrackFactory(artist=other_artist)

        listener = UserFactory()
        response = self.client.get(f"/api/albums/{album.id}/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {track["id"] for track in response.data["tracks"]}
        self.assertEqual(returned_ids, {str(own_track_a.id), str(own_track_b.id)})


class TrackSearchTests(APITestCase):
    def test_search_matches_title_and_artist_stage_name(self):
        artist = ArtistUserFactory()
        ArtistProfile.objects.filter(user=artist).update(stage_name="Neon Ray")
        TrackFactory(artist=artist, title="Some Song")
        other_artist = ArtistUserFactory()
        TrackFactory(artist=other_artist, title="Neon Skies")

        listener = UserFactory()
        response = self.client.get("/api/tracks/?search=neon", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class GoldGatedFieldsTests(APITestCase):
    def test_gold_only_aggregate_fields_absent_for_basic_listener(self):
        artist = ArtistUserFactory()
        TrackFactory(artist=artist)

        basic_listener = UserFactory()
        response = self.client.get(f"/api/artists/{artist.id}/", **auth_headers(basic_listener))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("total_plays", response.data)
        self.assertNotIn("total_listeners", response.data)

        gold_listener = UserFactory()
        SubscriptionFactory(user=gold_listener, plan__tier="gold", status="active")
        response = self.client.get(f"/api/artists/{artist.id}/", **auth_headers(gold_listener))
        self.assertIn("total_plays", response.data)
        self.assertIn("total_listeners", response.data)
