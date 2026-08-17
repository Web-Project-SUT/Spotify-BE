from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus, Role
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.services import record_stream
from apps.catalog.tests.factories import TrackFactory
from apps.subscriptions.models import Tier, Transaction
from apps.subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class AdminOverviewTests(APITestCase):
    def test_overview_shape_and_numbers_on_seeded_data(self):
        admin = UserFactory(role=Role.ADMIN, is_staff=True)
        listener = UserFactory()
        silver_plan = SubscriptionPlanFactory(tier=Tier.SILVER)
        silver = UserFactory()
        SubscriptionFactory(user=silver, plan=silver_plan, status="active")
        Transaction.objects.create(
            user=silver, plan=silver_plan, amount=Decimal("4.99"), status=Transaction.Status.SUCCESS
        )

        artist = ArtistUserFactory(status=AccountStatus.ACTIVE)
        ArtistUserFactory(status=AccountStatus.PENDING)
        track = TrackFactory(artist=artist)
        record_stream(user=listener, track=track)

        response = self.client.get("/api/reports/admin/overview/?months=3", **auth_headers(admin))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(len(data["revenue"]["series"]), 3)
        current_month_label = timezone.now().strftime("%Y-%m")
        self.assertEqual(data["revenue"]["series"][-1]["month"], current_month_label)
        self.assertEqual(Decimal(data["revenue"]["current_month"]), Decimal("4.99"))

        tiers = data["tier_distribution"]
        total_listeners = tiers["basic"] + tiers["silver"] + tiers["gold"]
        self.assertEqual(tiers["silver"], 1)
        # both `listener` (basic) and `silver` are listener-role users
        self.assertEqual(total_listeners, 2)

        totals = data["totals"]
        self.assertEqual(totals["artists"], 1)
        self.assertEqual(totals["pending_artists"], 1)
        self.assertGreaterEqual(totals["tracks"], 1)
        self.assertEqual(totals["streams_this_month"], 1)

    def test_support_gets_403(self):
        support = UserFactory(role=Role.SUPPORT)
        response = self.client.get("/api/reports/admin/overview/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listener_gets_403(self):
        listener = UserFactory()
        response = self.client.get("/api/reports/admin/overview/", **auth_headers(listener))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
