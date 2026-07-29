from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.services import record_stream
from apps.catalog.tests.factories import TrackFactory
from apps.reports import services
from apps.reports.models import PayoutPolicy
from apps.reports.tests.factories import PayoutPolicyFactory
from apps.subscriptions.models import Tier
from apps.subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory


class MonthBoundsTests(TestCase):
    def test_event_on_first_and_last_day_both_land_in_window(self):
        period = date(2026, 2, 1)
        since, until = services.month_bounds(period)

        from datetime import datetime

        first_instant = timezone.make_aware(datetime(2026, 2, 1, 0, 0, 0))
        last_instant = timezone.make_aware(datetime(2026, 2, 28, 23, 59, 59))

        self.assertTrue(since <= first_instant < until)
        self.assertTrue(since <= last_instant < until)
        self.assertEqual(since, timezone.make_aware(datetime(2026, 2, 1)))
        self.assertEqual(until, timezone.make_aware(datetime(2026, 3, 1)))

    def test_december_rolls_into_next_year(self):
        since, until = services.month_bounds(date(2026, 12, 1))
        from datetime import datetime

        self.assertEqual(until, timezone.make_aware(datetime(2027, 1, 1)))


class ParsePeriodTests(TestCase):
    def test_parses_year_month(self):
        self.assertEqual(services.parse_period("2026-07"), date(2026, 7, 1))

    def test_none_returns_none(self):
        self.assertIsNone(services.parse_period(None))

    def test_garbage_raises_validation_error(self):
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            services.parse_period("not-a-period")


class ArtistSummaryUniqueListenersTests(TestCase):
    def test_listeners_are_distinct_users_not_summed_per_track(self):
        artist = ArtistUserFactory()
        track_a = TrackFactory(artist=artist)
        track_b = TrackFactory(artist=artist)
        listener = UserFactory()
        other_listener = UserFactory()

        record_stream(user=listener, track=track_a)
        record_stream(user=listener, track=track_b)
        record_stream(user=other_listener, track=track_a)

        summary = services.artist_summary(artist=artist)
        self.assertEqual(summary["streams"], 3)
        self.assertEqual(summary["listeners"], 2)


class RevenueSeriesTests(TestCase):
    def test_series_pads_zero_months_and_ends_on_current_month(self):
        series = services.revenue_series(months=3)
        now = timezone.now()
        current_month_str = date(now.year, now.month, 1).strftime("%Y-%m")

        self.assertEqual(len(series), 3)
        self.assertEqual(series[-1]["month"], current_month_str)
        for entry in series:
            self.assertEqual(entry["amount"], Decimal("0"))


class TierDistributionTests(TestCase):
    def test_subscriptionless_listener_counts_as_basic(self):
        UserFactory()
        result = services.tier_distribution()
        self.assertEqual(result["basic"], 1)
        self.assertEqual(result["silver"], 0)
        self.assertEqual(result["gold"], 0)

    def test_ignores_artists_and_support(self):
        ArtistUserFactory()
        from apps.accounts.models import Role

        UserFactory(role=Role.SUPPORT)
        result = services.tier_distribution()
        self.assertEqual(result["basic"], 0)

    def test_expired_subscription_counts_as_basic(self):
        listener = UserFactory()
        plan = SubscriptionPlanFactory(tier=Tier.SILVER)
        SubscriptionFactory(
            user=listener,
            plan=plan,
            status="expired",
            expires_at=timezone.now() - timedelta(days=1),
        )
        result = services.tier_distribution()
        self.assertEqual(result["basic"], 1)
        self.assertEqual(result["silver"], 0)


class EarningsMathTests(TestCase):
    def test_earnings_use_effective_policy_rates(self):
        PayoutPolicy.objects.all().delete()
        PayoutPolicyFactory(per_stream_rate=Decimal("0.01"), per_listener_rate=Decimal("0.05"))

        artist = ArtistUserFactory()
        track = TrackFactory(artist=artist)
        listener_a = UserFactory()
        listener_b = UserFactory()
        record_stream(user=listener_a, track=track)
        record_stream(user=listener_b, track=track)

        summary = services.artist_summary(artist=artist)
        # 2 streams * 0.01 + 2 listeners * 0.05 = 0.02 + 0.10 = 0.12
        self.assertEqual(summary["streams"], 2)
        self.assertEqual(summary["listeners"], 2)
        self.assertEqual(summary["earnings"], Decimal("0.12"))
