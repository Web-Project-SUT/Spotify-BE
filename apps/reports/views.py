from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.catalog.models import Track
from apps.common.permissions import IsAdmin, IsArtist, IsSupportOrAdmin

from . import services
from .filters import ArtistPayoutFilterSet
from .models import ArtistPayout, PayoutPolicy
from .permissions import CanViewArtistStats
from .serializers import (
    AdminOverviewSerializer,
    ArtistOwnPayoutSerializer,
    ArtistPayoutSerializer,
    ArtistSummarySerializer,
    GeneratePayoutsResultSerializer,
    GeneratePayoutsSerializer,
    ListeningStatsSerializer,
    TrackStatSerializer,
)


def _artist_summary_payload(artist, request):
    period_str = request.query_params.get("period")
    period = services.parse_period(period_str)
    since = until = None
    if period is not None:
        since, until = services.month_bounds(period)
    data = services.artist_summary(artist=artist, since=since, until=until)
    data["period"] = period_str
    return data


class ListeningStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: ListeningStatsSerializer})
    def get(self, request):
        data = services.listening_stats(user=request.user)
        return Response(ListeningStatsSerializer(data).data)


class ArtistMeSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]

    @extend_schema(responses={200: ArtistSummarySerializer})
    def get(self, request):
        payload = _artist_summary_payload(request.user, request)
        return Response(ArtistSummarySerializer(payload).data)


class ArtistMeTracksView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]
    serializer_class = TrackStatSerializer
    # Plain annotation names — see the note in catalog.views.TrackViewSet:
    # ?ordering=-streams / -listeners / -earnings.
    ordering_fields = ["streams", "listeners", "earnings"]
    ordering = ["-streams"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Track.objects.none()
        period = services.parse_period(self.request.query_params.get("period"))
        since = until = None
        if period is not None:
            since, until = services.month_bounds(period)
        policy = PayoutPolicy.for_period(period or timezone.now().date())
        return services.track_stats(
            artist=self.request.user, since=since, until=until, policy=policy
        )


class ArtistMePayoutsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]
    serializer_class = ArtistOwnPayoutSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ArtistPayout.objects.none()
        return ArtistPayout.objects.filter(artist=self.request.user)


class ArtistSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanViewArtistStats]

    @extend_schema(responses={200: ArtistSummarySerializer})
    def get(self, request, pk):
        artist = get_object_or_404(User, pk=pk)
        payload = _artist_summary_payload(artist, request)
        return Response(ArtistSummarySerializer(payload).data)


class ArtistPayoutListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsSupportOrAdmin]
    serializer_class = ArtistPayoutSerializer
    filterset_class = ArtistPayoutFilterSet

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ArtistPayout.objects.none()
        return ArtistPayout.objects.select_related("artist__artist_profile")


class GeneratePayoutsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    @extend_schema(
        request=GeneratePayoutsSerializer, responses={200: GeneratePayoutsResultSerializer}
    )
    def post(self, request):
        serializer = GeneratePayoutsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        period = serializer.validated_data["period"] or services.previous_month()
        result = services.build_monthly_payouts(period=period)
        return Response(GeneratePayoutsResultSerializer(result).data)


class SettlePayoutView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    @extend_schema(request=None, responses={200: ArtistPayoutSerializer})
    def post(self, request, pk):
        payout = get_object_or_404(
            ArtistPayout.objects.select_related("artist__artist_profile"), pk=pk
        )
        if payout.status != ArtistPayout.Status.PAID:
            payout.status = ArtistPayout.Status.PAID
            payout.settled_at = timezone.now()
            payout.settled_by = request.user
            payout.save(update_fields=["status", "settled_at", "settled_by", "updated_at"])
        return Response(ArtistPayoutSerializer(payout).data)


class AdminOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    @extend_schema(responses={200: AdminOverviewSerializer})
    def get(self, request):
        try:
            months = int(request.query_params.get("months", 6))
        except (TypeError, ValueError):  # fmt: skip
            months = 6
        months = max(1, min(months, 24))

        revenue = services.revenue_summary()
        revenue["series"] = services.revenue_series(months=months)
        payload = {
            "revenue": revenue,
            "tier_distribution": services.tier_distribution(),
            "totals": services.platform_totals(),
        }
        return Response(AdminOverviewSerializer(payload).data)
