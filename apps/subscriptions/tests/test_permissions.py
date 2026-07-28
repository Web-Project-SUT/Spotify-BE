from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.subscriptions.models import SubscriptionPlan, Subscription, Tier
from apps.subscriptions.permissions import CanDownloadSong

User = get_user_model()

class SubscriptionPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="testuser", 
            email="test@example.com", 
            password="password123"
        )
        
        # ایجاد پلن پایه (بدون دسترسی دانلود)
        self.basic_plan = SubscriptionPlan.objects.create(
            tier=Tier.BASIC, 
            monthly_price=Decimal("0.00"), 
            can_download=False
        )
        
        # ایجاد پلن طلایی (با دسترسی دانلود)
        self.gold_plan = SubscriptionPlan.objects.create(
            tier=Tier.GOLD, 
            monthly_price=Decimal("9.99"), 
            can_download=True
        )
        
        self.permission = CanDownloadSong()

    def test_unauthenticated_user_denied(self):
        """کاربر بدون لاگین و اشتراک نباید دسترسی داشته باشد"""
        request = self.factory.get('/api/dummy/')
        request.user = self.user # کاربری که اشتراک ندارد
        self.assertFalse(self.permission.has_permission(request, None))

    def test_basic_plan_denied(self):
        """کاربر با پلن پایه نباید دسترسی دانلود داشته باشد"""
        Subscription.objects.create(
            user=self.user,
            plan=self.basic_plan,
            period_months=1,
            price_paid=Decimal("0.00"),
            starts_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
            status=Subscription.Status.ACTIVE
        )
        request = self.factory.get('/api/dummy/')
        request.user = self.user
        self.assertFalse(self.permission.has_permission(request, None))

    def test_gold_plan_allowed(self):
        """کاربر با پلن طلایی باید دسترسی دانلود داشته باشد"""
        Subscription.objects.create(
            user=self.user,
            plan=self.gold_plan,
            period_months=1,
            price_paid=Decimal("9.99"),
            starts_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
            status=Subscription.Status.ACTIVE
        )
        request = self.factory.get('/api/dummy/')
        request.user = self.user
        self.assertTrue(self.permission.has_permission(request, None))