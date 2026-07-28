from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel, UUIDModel


class Tier(models.TextChoices):
    SILVER = "silver", "Silver"
    GOLD = "gold", "Gold"


class SubscriptionPlan(TimeStampedModel):
    tier = models.CharField(max_length=8, choices=Tier.choices, unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.tier


class Subscription(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    period_months = models.PositiveSmallIntegerField(
        choices=[(1, "1"), (3, "3"), (6, "6"), (12, "12")]
    )
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)

    class Meta:
        indexes = [models.Index(fields=["user", "status", "expires_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status="active"),
                name="one_active_subscription",
            )
        ]
