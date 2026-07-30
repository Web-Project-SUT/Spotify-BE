from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class PayoutPolicy(TimeStampedModel):
    per_stream_rate = models.DecimalField(max_digits=12, decimal_places=6)
    per_listener_rate = models.DecimalField(max_digits=12, decimal_places=6)
    effective_from = models.DateField(unique=True)

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return f"policy effective {self.effective_from}"

    @classmethod
    def for_period(cls, period_month):
        return cls.objects.filter(effective_from__lte=period_month).first()


class ArtistPayout(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"

    artist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payouts"
    )
    period_month = models.DateField(db_index=True)
    unique_listeners = models.PositiveIntegerField()
    streams = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    policy = models.ForeignKey(
        PayoutPolicy, on_delete=models.SET_NULL, null=True, related_name="payouts"
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    settled_at = models.DateTimeField(null=True, blank=True)
    settled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payouts_settled",
    )

    class Meta:
        ordering = ["-period_month", "artist_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["artist", "period_month"], name="uniq_artist_payout_period"
            )
        ]
        indexes = [models.Index(fields=["period_month", "status"])]

    def __str__(self):
        return f"{self.artist_id} - {self.period_month} - {self.status}"
