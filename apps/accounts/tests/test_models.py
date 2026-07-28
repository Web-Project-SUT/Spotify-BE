from django.db import IntegrityError
from rest_framework.test import APITestCase

from apps.accounts.models import Follow
from apps.accounts.tests.factories import UserFactory
from apps.subscriptions.tests.factories import SubscriptionFactory


class UserModelTests(APITestCase):
    def test_username_uniqueness_enforced(self):
        UserFactory(username="nova_ray")
        with self.assertRaises(IntegrityError):
            UserFactory(username="nova_ray", email="other@demo.com")

    def test_tier_falls_back_to_basic_without_subscription(self):
        user = UserFactory()
        self.assertEqual(user.tier, "basic")

    def test_tier_falls_back_to_basic_with_expired_subscription(self):
        user = UserFactory()
        SubscriptionFactory(user=user, status="expired")
        self.assertEqual(user.tier, "basic")


class FollowModelTests(APITestCase):
    def test_no_self_follow_constraint(self):
        user = UserFactory()
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=user, following=user)

    def test_uniq_follow_constraint(self):
        a, b = UserFactory(), UserFactory()
        Follow.objects.create(follower=a, following=b)
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=a, following=b)
