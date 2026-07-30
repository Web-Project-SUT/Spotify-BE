from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.models import PlayEvent
from apps.catalog.services import record_stream
from apps.catalog.tests.factories import TrackFactory
from apps.subscriptions.models import Tier
from apps.subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


def make_gold_listener():
    listener = UserFactory()
    plan = SubscriptionPlanFactory(tier=Tier.GOLD)
    SubscriptionFactory(user=listener, plan=plan, status="active")
    return listener


class ArtistMeTracksScopeTests(APITestCase):
    def test_artist_sees_only_their_own_tracks(self):
        artist = ArtistUserFactory()
        other_artist = ArtistUserFactory()
        own_track = TrackFactory(artist=artist)
        TrackFactory(artist=other_artist)

        response = self.client.get("/api/reports/artists/me/tracks/", **auth_headers(artist))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {row["id"] for row in response.data["results"]}
        self.assertEqual(returned_ids, {str(own_track.id)})

    def test_listener_gets_403(self):
        listener = UserFactory()
        response = self.client.get("/api/reports/artists/me/tracks/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ArtistMeSummaryPeriodTests(APITestCase):
    def test_period_narrows_the_window(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        listener = UserFactory()
        event = record_stream(user=listener, track=track)
        old_month = (timezone.now() - timedelta(days=60)).strftime("%Y-%m")
        PlayEvent.objects.filter(pk=event.pk).update(
            played_at=timezone.now() - timedelta(days=60)
        )

        current_response = self.client.get(
            f"/api/reports/artists/me/summary/?period={timezone.now().strftime('%Y-%m')}",
            **auth_headers(artist),
        )
        old_response = self.client.get(
            f"/api/reports/artists/me/summary/?period={old_month}", **auth_headers(artist)
        )

        self.assertEqual(current_response.data["total_streams"], 0)
        self.assertEqual(old_response.data["total_streams"], 1)

    def test_listener_gets_403_on_artists_me_summary(self):
        listener = UserFactory()
        response = self.client.get("/api/reports/artists/me/summary/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ArtistSummaryPermissionTests(APITestCase):
    def test_gold_listener_can_read_another_artists_summary(self):
        artist = ArtistUserFactory()
        gold = make_gold_listener()

        response = self.client.get(
            f"/api/reports/artists/{artist.id}/summary/", **auth_headers(gold)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_basic_listener_gets_403(self):
        artist = ArtistUserFactory()
        basic = UserFactory()

        response = self.client.get(
            f"/api/reports/artists/{artist.id}/summary/", **auth_headers(basic)
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_artist_can_read_own_summary_without_being_gold(self):
        artist = ArtistUserFactory()

        response = self.client.get(
            f"/api/reports/artists/{artist.id}/summary/", **auth_headers(artist)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_support_and_admin_can_read_any_artist_summary(self):
        artist = ArtistUserFactory()
        support = UserFactory(role=Role.SUPPORT)
        admin = UserFactory(role=Role.ADMIN, is_staff=True)

        support_response = self.client.get(
            f"/api/reports/artists/{artist.id}/summary/", **auth_headers(support)
        )
        admin_response = self.client.get(
            f"/api/reports/artists/{artist.id}/summary/", **auth_headers(admin)
        )

        self.assertEqual(support_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
