from rest_framework import serializers

from .models import PERIOD_MONTHS_CHOICES, SubscriptionPlan


class PaymentStartSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(
        source="plan", queryset=SubscriptionPlan.objects.all()
    )
    period_months = serializers.ChoiceField(
        choices=[c[0] for c in PERIOD_MONTHS_CHOICES], default=1
    )


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "tier",
            "monthly_price",
            "daily_stream_limit",
            "playlist_limit",
            "can_add_avatar",
            "can_download",
            "has_early_access",
            "can_view_stats",
        ]


class PlanPriceUpdateSerializer(serializers.ModelSerializer):
    """Admin-only price edit (Task 29 — dynamic subscription pricing).

    Only monthly_price is writable; every other field stays read-only so a
    price change can never accidentally alter a plan's tier or limits.
    """

    class Meta:
        model = SubscriptionPlan
        fields = SubscriptionPlanSerializer.Meta.fields
        read_only_fields = [f for f in fields if f != "monthly_price"]
