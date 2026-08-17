from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.tests.factories import AlbumFactory, TrackFactory
from apps.subscriptions.tests.factories import SubscriptionFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


FUTURE = timezone.now() + timezone.timedelta(days=30)
PAST = timezone.now() - timezone.timedelta(days=1)


class TrackListEarlyAccessTests(APITestCase):
    def test_basic_listener_does_not_see_embargoed_track(self):
        track = TrackFactory(early_access_until=FUTURE)
        basic_listener = UserFactory()

        response = self.client.get("/api/tracks/", **auth_headers(basic_listener))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertNotIn(str(track.id), ids)

    def test_gold_listener_sees_embargoed_track(self):
        track = TrackFactory(early_access_until=FUTURE)
        gold_listener = UserFactory()
        SubscriptionFactory(user=gold_listener, plan__tier="gold", status="active")

        response = self.client.get("/api/tracks/", **auth_headers(gold_listener))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(track.id), ids)

    def test_artist_sees_their_own_embargoed_track_but_not_anothers(self):
        artist = ArtistUserFactory()
        own_track = TrackFactory(artist=artist, early_access_until=FUTURE)
        other_track = TrackFactory(early_access_until=FUTURE)

        response = self.client.get("/api/tracks/", **auth_headers(artist))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(own_track.id), ids)
        self.assertNotIn(str(other_track.id), ids)

    def test_support_sees_every_embargoed_track(self):
        track = TrackFactory(early_access_until=FUTURE)
        support = UserFactory(role="support")

        response = self.client.get("/api/tracks/", **auth_headers(support))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(track.id), ids)

    def test_early_access_true_filter_returns_only_embargoed(self):
        embargoed = TrackFactory(early_access_until=FUTURE)
        TrackFactory(early_access_until=None)
        gold_listener = UserFactory()
        SubscriptionFactory(user=gold_listener, plan__tier="gold", status="active")

        response = self.client.get("/api/tracks/?earlyAccess=true", **auth_headers(gold_listener))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {str(embargoed.id)})

    def test_early_access_false_filter_excludes_embargoed(self):
        TrackFactory(early_access_until=FUTURE)
        released = TrackFactory(early_access_until=PAST)
        never_gated = TrackFactory(early_access_until=None)
        gold_listener = UserFactory()
        SubscriptionFactory(user=gold_listener, plan__tier="gold", status="active")

        response = self.client.get("/api/tracks/?earlyAccess=false", **auth_headers(gold_listener))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertEqual(ids, {str(released.id), str(never_gated.id)})


class AlbumDetailEarlyAccessTests(APITestCase):
    def test_basic_listener_does_not_see_embargoed_track_in_album_detail(self):
        artist = ArtistUserFactory()
        album = AlbumFactory(artist=artist)
        visible = TrackFactory(artist=artist, album=album)
        embargoed = TrackFactory(artist=artist, album=album, early_access_until=FUTURE)

        basic_listener = UserFactory()
        response = self.client.get(f"/api/albums/{album.id}/", **auth_headers(basic_listener))
        ids = {row["id"] for row in response.data["tracks"]}
        self.assertEqual(ids, {str(visible.id)})
        self.assertNotIn(str(embargoed.id), ids)


class RecommendationsEarlyAccessTests(APITestCase):
    def test_basic_listener_does_not_get_embargoed_recommendations(self):
        TrackFactory(early_access_until=FUTURE)
        basic_listener = UserFactory()

        response = self.client.get("/api/recommendations/", **auth_headers(basic_listener))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
