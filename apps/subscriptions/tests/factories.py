from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.subscriptions.models import Subscription, SubscriptionPlan, Tier


class SubscriptionPlanFactory(DjangoModelFactory):
    class Meta:
        model = SubscriptionPlan
        django_get_or_create = ("tier",)

    tier = Tier.SILVER
    monthly_price = Decimal("4.99")


class SubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = Subscription

    user = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    plan = factory.SubFactory(SubscriptionPlanFactory)
    period_months = 1
    price_paid = Decimal("4.99")
    starts_at = factory.LazyFunction(timezone.now)
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    status = Subscription.Status.ACTIVE
