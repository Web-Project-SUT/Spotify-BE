from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Notification
from apps.subscriptions import services
from apps.subscriptions.models import Subscription
from apps.subscriptions.tests.factories import SubscriptionFactory


class ExpireSubscriptionsTests(TestCase):
    def test_flips_a_lapsed_active_row_to_expired(self):
        past = timezone.now() - timedelta(days=1)
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE, expires_at=past)

        result = services.expire_subscriptions()

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.EXPIRED)
        self.assertEqual(result["expired"], 1)

    def test_leaves_a_still_active_row_alone(self):
        future = timezone.now() + timedelta(days=30)
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE, expires_at=future)

        services.expire_subscriptions()

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

    def test_warns_a_subscription_expiring_within_the_window(self):
        soon = timezone.now() + timedelta(days=1)
        sub = SubscriptionFactory(status=Subscription.Status.ACTIVE, expires_at=soon)

        result = services.expire_subscriptions()

        self.assertEqual(result["warned"], 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=sub.user, type="subscription", link="/upgrade"
            ).exists()
        )

    def test_does_not_warn_twice_for_the_same_subscription_period(self):
        soon = timezone.now() + timedelta(days=1)
        SubscriptionFactory(status=Subscription.Status.ACTIVE, expires_at=soon)

        first = services.expire_subscriptions()
        second = services.expire_subscriptions()

        self.assertEqual(first["warned"], 1)
        self.assertEqual(second["warned"], 0)

    def test_does_not_warn_a_subscription_outside_the_window(self):
        far_off = timezone.now() + timedelta(days=30)
        SubscriptionFactory(status=Subscription.Status.ACTIVE, expires_at=far_off)

        result = services.expire_subscriptions()

        self.assertEqual(result["warned"], 0)

    def test_management_command_runs(self):
        past = timezone.now() - timedelta(days=1)
        SubscriptionFactory(status=Subscription.Status.ACTIVE, expires_at=past)
        call_command("expire_subscriptions")
        self.assertTrue(Subscription.objects.filter(status=Subscription.Status.EXPIRED).exists())
