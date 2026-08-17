from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class Tier(models.TextChoices):
    BASIC = "basic", "Base (Free)"
    SILVER = "silver", "Silver"
    GOLD = "gold", "Gold"


# The only durations a subscription can be purchased for (doc.tex §3.2).
# Shared by Subscription.period_months and Transaction.period_months so the
# set of valid durations lives in exactly one place.
PERIOD_MONTHS_CHOICES = [(1, "1"), (3, "3"), (6, "6"), (12, "12")]


class SubscriptionPlan(TimeStampedModel):
    tier = models.CharField(max_length=8, choices=Tier.choices, unique=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    
    # Task 28 limits (Null means unlimited)
    daily_stream_limit = models.IntegerField(null=True, blank=True, help_text="Null means unlimited")
    playlist_limit = models.IntegerField(null=True, blank=True, help_text="Null means unlimited")
    
    # Access control flags
    can_add_avatar = models.BooleanField(default=False)
    can_download = models.BooleanField(default=False)
    has_early_access = models.BooleanField(default=False)
    can_view_stats = models.BooleanField(default=False)

    def __str__(self):
        return self.get_tier_display()


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
    period_months = models.PositiveSmallIntegerField(choices=PERIOD_MONTHS_CHOICES)
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

    def is_valid(self):
        if self.status != self.Status.ACTIVE:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
class Transaction(TimeStampedModel, UUIDModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="transactions"
    )
    # The duration the user picked at checkout — has to survive the
    # redirect round-trip to the payment callback, and nothing else carries
    # it (the callback only gets `authority` and `Status` back from Zarinpal).
    period_months = models.PositiveSmallIntegerField(choices=PERIOD_MONTHS_CHOICES, default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    authority = models.CharField(max_length=100, null=True, blank=True)
    ref_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    def __str__(self):
        return f"{self.user} - {self.plan.tier} - {self.status}"