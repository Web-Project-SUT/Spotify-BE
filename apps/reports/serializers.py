from rest_framework import serializers

from .models import ArtistPayout


class ListeningStatsSerializer(serializers.Serializer):
    streams_today = serializers.IntegerField()
    streams_this_month = serializers.IntegerField()
    daily_limit = serializers.IntegerField(allow_null=True)
    remaining_today = serializers.IntegerField(allow_null=True)


class TopTrackSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    streams = serializers.IntegerField()


class ArtistSummarySerializer(serializers.Serializer):
    period = serializers.CharField(allow_null=True)
    total_streams = serializers.IntegerField(source="streams")
    total_listeners = serializers.IntegerField(source="listeners")
    total_earnings = serializers.DecimalField(source="earnings", max_digits=12, decimal_places=2)
    top_track = TopTrackSerializer(allow_null=True)


class TrackStatSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    cover = serializers.ImageField(allow_null=True, use_url=True)
    stream_count = serializers.IntegerField(source="streams")
    listener_count = serializers.IntegerField(source="listeners")
    earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    released_at = serializers.DateTimeField()


class ArtistOwnPayoutSerializer(serializers.ModelSerializer):
    listeners = serializers.IntegerField(source="unique_listeners")

    class Meta:
        model = ArtistPayout
        fields = ["period_month", "listeners", "streams", "amount", "status", "settled_at"]


class ArtistPayoutSerializer(serializers.ModelSerializer):
    artist_id = serializers.UUIDField(read_only=True)
    artist_name = serializers.SerializerMethodField()
    listeners = serializers.IntegerField(source="unique_listeners")

    class Meta:
        model = ArtistPayout
        fields = [
            "id",
            "artist_id",
            "artist_name",
            "listeners",
            "streams",
            "amount",
            "status",
            "period_month",
            "settled_at",
        ]

    def get_artist_name(self, obj) -> str:
        artist = obj.artist
        profile = getattr(artist, "artist_profile", None)
        if profile is not None and profile.stage_name:
            return profile.stage_name
        return artist.display_name


class RevenueSeriesItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class RevenueSerializer(serializers.Serializer):
    current_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_subscriptions = serializers.IntegerField()
    series = RevenueSeriesItemSerializer(many=True)


class TierDistributionSerializer(serializers.Serializer):
    basic = serializers.IntegerField()
    silver = serializers.IntegerField()
    gold = serializers.IntegerField()


class PlatformTotalsSerializer(serializers.Serializer):
    users = serializers.IntegerField()
    listeners = serializers.IntegerField()
    artists = serializers.IntegerField()
    pending_artists = serializers.IntegerField()
    tracks = serializers.IntegerField()
    albums = serializers.IntegerField()
    streams_this_month = serializers.IntegerField()


class AdminOverviewSerializer(serializers.Serializer):
    revenue = RevenueSerializer()
    tier_distribution = TierDistributionSerializer()
    totals = PlatformTotalsSerializer()


class GeneratePayoutsSerializer(serializers.Serializer):
    period = serializers.CharField(required=False, allow_null=True, default=None)

    def validate_period(self, value):
        from . import services

        return services.parse_period(value)


class GeneratePayoutsResultSerializer(serializers.Serializer):
    period = serializers.DateField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    skipped_settled = serializers.IntegerField()
