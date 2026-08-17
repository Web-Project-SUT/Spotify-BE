from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.subscriptions.models import Subscription, SubscriptionPlan, Tier

User = get_user_model()


class SubscriptionPlanModelTest(TestCase):
    def test_create_plan(self):
        # The per-tier limits and entitlement flags were removed in D-2 (they
        # were never read by the running rules, which live in apps/common), so a
        # plan now carries only tier, price and active state.
        plan = SubscriptionPlan.objects.create(
            tier=Tier.GOLD,
            monthly_price=Decimal("9.99"),
        )
        self.assertEqual(plan.tier, Tier.GOLD)
        self.assertEqual(plan.monthly_price, Decimal("9.99"))
        self.assertTrue(plan.is_active)

    def test_tier_is_unique(self):
        SubscriptionPlan.objects.create(tier=Tier.BASIC, monthly_price=Decimal("0.00"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubscriptionPlan.objects.create(tier=Tier.BASIC, monthly_price=Decimal("1.00"))


class SubscriptionModelTest(TestCase):
    def setUp(self):
        # ایجاد داده‌های پایه برای تست‌ها
        self.user = User.objects.create_user(
            email="testuser@example.com", password="testpassword123", username="testuser"
        )
        self.plan = SubscriptionPlan.objects.create(tier=Tier.SILVER, monthly_price=Decimal("4.99"))

    def test_subscription_is_valid_active(self):
        """تست معتبر بودن اشتراک فعال"""
        future_date = timezone.now() + timedelta(days=30)
        sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=1,
            price_paid=Decimal("4.99"),
            starts_at=timezone.now(),
            expires_at=future_date,
            status=Subscription.Status.ACTIVE,
        )
        self.assertTrue(sub.is_valid())

    def test_subscription_invalid_past_expires_at(self):
        """تست نامعتبر بودن اشتراکی که تاریخ انقضای آن گذشته است"""
        past_date = timezone.now() - timedelta(days=1)
        sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=1,
            price_paid=Decimal("4.99"),
            starts_at=timezone.now() - timedelta(days=30),
            expires_at=past_date,
            status=Subscription.Status.ACTIVE,
        )
        self.assertFalse(sub.is_valid())

    def test_subscription_invalid_if_expired_status(self):
        """تست نامعتبر بودن اشتراکی که وضعیت آن منقضی شده است"""
        future_date = timezone.now() + timedelta(days=30)
        sub = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=1,
            price_paid=Decimal("4.99"),
            starts_at=timezone.now(),
            expires_at=future_date,
            status=Subscription.Status.EXPIRED,
        )
        self.assertFalse(sub.is_valid())

    def test_one_active_subscription_constraint(self):
        """تست جلوگیری از داشتن دو اشتراک فعال همزمان برای یک کاربر"""
        future_date = timezone.now() + timedelta(days=30)

        # ثبت اولین اشتراک فعال
        Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=1,
            price_paid=Decimal("4.99"),
            starts_at=timezone.now(),
            expires_at=future_date,
            status=Subscription.Status.ACTIVE,
        )

        # تلاش برای ثبت دومین اشتراک فعال که باید با ارور روبرو شود
        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                user=self.user,
                plan=self.plan,
                period_months=1,
                price_paid=Decimal("4.99"),
                starts_at=timezone.now(),
                expires_at=future_date,
                status=Subscription.Status.ACTIVE,
            )
