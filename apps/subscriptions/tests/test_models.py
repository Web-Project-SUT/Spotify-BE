from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.tests.factories import UserFactory
from apps.subscriptions.tests.factories import SubscriptionFactory


class SubscriptionModelTests(APITestCase):
    def test_one_active_subscription_partial_unique(self):
        user = UserFactory()
        SubscriptionFactory(user=user, status="active")
        with self.assertRaises(IntegrityError):
            SubscriptionFactory(user=user, status="active")

    def test_multiple_non_active_subscriptions_allowed(self):
        user = UserFactory()
        SubscriptionFactory(
            user=user,
            status="expired",
            expires_at=timezone.now() - timedelta(days=1),
        )
        SubscriptionFactory(
            user=user,
            status="expired",
            expires_at=timezone.now() - timedelta(days=2),
        )
