from datetime import date
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.services import record_stream
from apps.catalog.tests.factories import TrackFactory
from apps.reports import services
from apps.reports.models import ArtistPayout, PayoutPolicy
from apps.reports.tests.factories import ArtistPayoutFactory, PayoutPolicyFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class BuildMonthlyPayoutsTests(APITestCase):
    def setUp(self):
        PayoutPolicy.objects.all().delete()
        PayoutPolicyFactory()

    def test_idempotent_rerun_does_not_duplicate(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        listener = UserFactory()
        record_stream(user=listener, track=track)

        period = date.today().replace(day=1)
        first = services.build_monthly_payouts(period=period)
        second = services.build_monthly_payouts(period=period)

        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["updated"], 1)
        self.assertEqual(ArtistPayout.objects.filter(artist=artist, period_month=period).count(), 1)

    def test_rerun_does_not_touch_paid_row(self):
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        listener = UserFactory()
        record_stream(user=listener, track=track)

        period = date.today().replace(day=1)
        services.build_monthly_payouts(period=period)
        payout = ArtistPayout.objects.get(artist=artist, period_month=period)
        payout.status = ArtistPayout.Status.PAID
        payout.amount = Decimal("999.99")
        payout.save()

        result = services.build_monthly_payouts(period=period)
        payout.refresh_from_db()

        self.assertEqual(result["skipped_settled"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(payout.amount, Decimal("999.99"))


class GeneratePayoutsViewTests(APITestCase):
    def setUp(self):
        PayoutPolicy.objects.all().delete()
        PayoutPolicyFactory()

    def test_support_cannot_generate(self):
        support = UserFactory(role=Role.SUPPORT)
        response = self.client.post(
            "/api/reports/payouts/generate/",
            {"period": date.today().strftime("%Y-%m")},
            format="json",
            **auth_headers(support),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_generate(self):
        admin = UserFactory(role=Role.ADMIN, is_staff=True)
        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        listener = UserFactory()
        record_stream(user=listener, track=track)

        response = self.client.post(
            "/api/reports/payouts/generate/",
            {"period": date.today().strftime("%Y-%m")},
            format="json",
            **auth_headers(admin),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], 1)


class SettlePayoutViewTests(APITestCase):
    def test_settle_flips_to_paid_and_stamps_settler(self):
        admin = UserFactory(role=Role.ADMIN, is_staff=True)
        payout = ArtistPayoutFactory(status=ArtistPayout.Status.PENDING)

        response = self.client.post(
            f"/api/reports/payouts/{payout.id}/settle/", **auth_headers(admin)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payout.refresh_from_db()
        self.assertEqual(payout.status, ArtistPayout.Status.PAID)
        self.assertEqual(payout.settled_by, admin)
        self.assertIsNotNone(payout.settled_at)

    def test_second_settle_is_noop_200(self):
        admin = UserFactory(role=Role.ADMIN, is_staff=True)
        payout = ArtistPayoutFactory(status=ArtistPayout.Status.PENDING)

        self.client.post(f"/api/reports/payouts/{payout.id}/settle/", **auth_headers(admin))
        payout.refresh_from_db()
        first_settled_at = payout.settled_at

        response = self.client.post(
            f"/api/reports/payouts/{payout.id}/settle/", **auth_headers(admin)
        )
        payout.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payout.settled_at, first_settled_at)

    def test_support_can_list_but_not_settle(self):
        support = UserFactory(role=Role.SUPPORT)
        payout = ArtistPayoutFactory(status=ArtistPayout.Status.PENDING)

        list_response = self.client.get("/api/reports/payouts/", **auth_headers(support))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        settle_response = self.client.post(
            f"/api/reports/payouts/{payout.id}/settle/", **auth_headers(support)
        )
        self.assertEqual(settle_response.status_code, status.HTTP_403_FORBIDDEN)
