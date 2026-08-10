from rest_framework import serializers

from .models import SubscriptionPlan


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
