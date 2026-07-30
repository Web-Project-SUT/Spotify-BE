from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response

from apps.common.permissions import IsApprovedArtist

from .filters import TrackFilterSet
from .models import Album, Track
from .permissions import IsArtistOwner
from .serializers import (
    AlbumDetailSerializer,
    AlbumListSerializer,
    AlbumWriteSerializer,
    StreamCreateSerializer,
    StreamSerializer,
    TrackListSerializer,
    TrackWriteSerializer,
)
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.playlists.models import Playlist

class AlbumViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        queryset = Album.objects.select_related("artist")
        if self.action != "list":
            queryset = queryset.prefetch_related("tracks")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return AlbumListSerializer
        if self.action in ("create", "update", "partial_update"):
            return AlbumWriteSerializer
        return AlbumDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsApprovedArtist()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsArtistOwner()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(artist=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = AlbumDetailSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output = AlbumDetailSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data)


class TrackViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    filterset_class = TrackFilterSet
    search_fields = ["title", "artist__artist_profile__stage_name"]
    ordering_fields = [
        ("play_count", "playCount"),
        ("released_at", "releasedAt"),
    ]
    ordering = ["-released_at"]

    def get_queryset(self):
        return Track.objects.select_related("artist", "album")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TrackWriteSerializer
        return TrackListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsApprovedArtist()]
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsArtistOwner()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(artist=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = TrackListSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output = TrackListSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data)


class StreamCreateView(generics.CreateAPIView):
    serializer_class = StreamCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response(StreamSerializer(event).data, status=status.HTTP_201_CREATED)


class RecommendationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # جستجو در مدل واسط (entries) برای پیدا کردن هنرمندان
        user_playlists = Playlist.objects.filter(owner=user).prefetch_related('entries__track__artist')
        liked_artists = set()
        
        for playlist in user_playlists:
            for entry in playlist.entries.all():
                if entry.track and entry.track.artist:
                    liked_artists.add(entry.track.artist.id)
        
        # اگر کاربر سابقه داشت، آهنگ‌های همان هنرمندان را پیشنهاد بده
        if liked_artists:
            recommended_tracks = Track.objects.filter(artist_id__in=liked_artists).distinct()[:10]
        # در غیر این صورت، جدیدترین آهنگ‌ها را برگردان
        else:
            recommended_tracks = Track.objects.all().order_by('-created_at')[:10]
            
        # استفاده از نام درست سریالایزر پروژه شما
        serializer = TrackListSerializer(recommended_tracks, many=True)
        return Response(serializer.data)