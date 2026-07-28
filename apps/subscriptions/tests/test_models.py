from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from apps.subscriptions.models import SubscriptionPlan, Subscription, Tier

User = get_user_model()

class SubscriptionPlanModelTest(TestCase):
    def test_create_basic_plan_with_limits(self):
        """تست ایجاد اشتراک پایه با محدودیت‌های مشخص شده"""
        plan = SubscriptionPlan.objects.create(
            tier=Tier.BASIC,
            monthly_price=Decimal("0.00"),
            daily_stream_limit=60,
            playlist_limit=6,
            can_add_avatar=False,
            can_download=False,
            has_early_access=False,
            can_view_stats=False
        )
        self.assertEqual(plan.daily_stream_limit, 60)
        self.assertEqual(plan.playlist_limit, 6)
        self.assertFalse(plan.can_download)

    def test_create_gold_plan_unlimited(self):
        """تست ایجاد اشتراک طلایی با محدودیت‌های نامحدود (Null) و دسترسی کامل"""
        plan = SubscriptionPlan.objects.create(
            tier=Tier.GOLD,
            monthly_price=Decimal("9.99"),
            daily_stream_limit=None,
            playlist_limit=None,
            can_add_avatar=True,
            can_download=True,
            has_early_access=True,
            can_view_stats=True
        )
        self.assertIsNone(plan.daily_stream_limit)
        self.assertIsNone(plan.playlist_limit)
        self.assertTrue(plan.has_early_access)


class SubscriptionModelTest(TestCase):
    def setUp(self):
        # ایجاد داده‌های پایه برای تست‌ها
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpassword123",
            username="testuser"
        )
        self.plan = SubscriptionPlan.objects.create(
            tier=Tier.SILVER,
            monthly_price=Decimal("4.99")
        )

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
            status=Subscription.Status.ACTIVE
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
            status=Subscription.Status.ACTIVE
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
            status=Subscription.Status.EXPIRED
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
            status=Subscription.Status.ACTIVE
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
                status=Subscription.Status.ACTIVE
            )