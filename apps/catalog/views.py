import mimetypes

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.http import range_file_response
from apps.common.openapi import Params, Responses, Tags, media_resource_schema
from apps.common.permissions import IsApprovedArtist, IsSilverOrAbove
from apps.common.views import MediaResourceView

from .filters import TrackFilterSet
from .models import Album, Track
from .permissions import IsArtistOwner
from .serializers import (
    AlbumCoverUploadSerializer,
    AlbumDetailSerializer,
    AlbumListSerializer,
    AlbumWriteSerializer,
    StreamCreateSerializer,
    StreamSerializer,
    TrackAudioUploadSerializer,
    TrackCoverUploadSerializer,
    TrackListSerializer,
    TrackWriteSerializer,
)
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.playlists.models import Playlist

@extend_schema_view(
    list=extend_schema(
        tags=[Tags.ALBUMS], summary="List albums", parameters=[Params.PAGE, Params.PAGE_SIZE]
    ),
    retrieve=extend_schema(
        tags=[Tags.ALBUMS], summary="Get an album", responses={404: Responses.NOT_FOUND_404}
    ),
    create=extend_schema(
        tags=[Tags.ALBUMS],
        summary="Create an album",
        description="Approved artists only.",
        responses={
            201: AlbumDetailSerializer,
            400: Responses.VALIDATION_400,
            403: Responses.FORBIDDEN_403,
        },
    ),
    partial_update=extend_schema(
        tags=[Tags.ALBUMS],
        summary="Update an album",
        description="Album owner only.",
        responses={
            200: AlbumDetailSerializer,
            400: Responses.VALIDATION_400,
            403: Responses.FORBIDDEN_403,
            404: Responses.NOT_FOUND_404,
        },
    ),
    destroy=extend_schema(
        tags=[Tags.ALBUMS],
        summary="Delete an album",
        description="Album owner only.",
        responses={403: Responses.FORBIDDEN_403, 404: Responses.NOT_FOUND_404},
    ),
)
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


@extend_schema_view(
    list=extend_schema(
        tags=[Tags.TRACKS],
        summary="List/search/sort tracks",
        description=(
            "`?search` matches track title or artist stage name. `?genre` and `?artist` (UUID) "
            "filter exactly. `?earlyAccess=true` restricts to tracks still within their "
            "early-access window (`doc.tex` §2.9's Gold-only home page section)."
        ),
        parameters=[
            Params.ORDERING("playCount", "-playCount", "releasedAt", "-releasedAt"),
            Params.PAGE,
            Params.PAGE_SIZE,
        ],
    ),
    retrieve=extend_schema(
        tags=[Tags.TRACKS], summary="Get a track", responses={404: Responses.NOT_FOUND_404}
    ),
    create=extend_schema(
        tags=[Tags.TRACKS],
        summary="Create a track",
        description="Approved artists only.",
        responses={
            201: TrackListSerializer,
            400: Responses.VALIDATION_400,
            403: Responses.FORBIDDEN_403,
        },
    ),
    partial_update=extend_schema(
        tags=[Tags.TRACKS],
        summary="Update a track",
        description="Track owner only.",
        responses={
            200: TrackListSerializer,
            400: Responses.VALIDATION_400,
            403: Responses.FORBIDDEN_403,
            404: Responses.NOT_FOUND_404,
        },
    ),
    destroy=extend_schema(
        tags=[Tags.TRACKS],
        summary="Delete a track",
        description="Track owner only.",
        responses={403: Responses.FORBIDDEN_403, 404: Responses.NOT_FOUND_404},
    ),
)
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


@extend_schema_view(
    post=extend_schema(
        tags=[Tags.STREAMING],
        summary="Record a play event",
        description=(
            "Called by the player on playback start; `playlist` is optional context for the "
            "`?recent` ordering."
        ),
        responses={201: StreamSerializer, 400: Responses.VALIDATION_400},
    )
)
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

    @extend_schema(
        tags=[Tags.RECOMMENDATIONS],
        summary="Get personalized track recommendations",
        description=(
            "Looks at the artists behind tracks already in the user's playlists; if that set "
            "is non-empty, returns up to 10 other tracks by those artists, else falls back to "
            "the 10 newest tracks platform-wide. **Unlike every other list endpoint, this one "
            "is unpaginated and hard-capped at 10** — there is no `?page`/`?pageSize`."
        ),
        responses={200: TrackListSerializer(many=True)},
    )
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
@media_resource_schema(
    AlbumDetailSerializer,
    AlbumCoverUploadSerializer,
    summary_noun="album cover",
    tags=[Tags.ALBUMS],
)
class AlbumCoverView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated, IsArtistOwner]
    queryset = Album.objects.all()
    media_fields = ("cover",)
    upload_serializer_class = AlbumCoverUploadSerializer
    read_serializer_class = AlbumDetailSerializer


@media_resource_schema(
    TrackListSerializer, TrackCoverUploadSerializer, summary_noun="track cover", tags=[Tags.TRACKS]
)
class TrackCoverView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated, IsArtistOwner]
    queryset = Track.objects.all()
    media_fields = ("cover",)
    upload_serializer_class = TrackCoverUploadSerializer
    read_serializer_class = TrackListSerializer


@media_resource_schema(
    TrackListSerializer,
    TrackAudioUploadSerializer,
    summary_noun="track audio",
    tags=[Tags.TRACKS],
)
class TrackAudioView(MediaResourceView):
    """`audioHigh` and `audioLow` are both required in the one multipart request — the player's
    quality switch (`doc.tex` §5.1) needs both bitrates present from the start. Content is
    verified by magic-byte sniffing (`apps.common.validators.AudioSignature`), not the
    client-supplied `Content-Type`, which is trivially spoofed.
    """

    permission_classes = [permissions.IsAuthenticated, IsApprovedArtist, IsArtistOwner]
    queryset = Track.objects.all()
    media_fields = ("audio_high", "audio_low")
    upload_serializer_class = TrackAudioUploadSerializer
    read_serializer_class = TrackListSerializer


class TrackDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSilverOrAbove]

    @extend_schema(
        tags=[Tags.STREAMING],
        summary="Download a track's high-quality audio",
        description=(
            "Silver/Gold tiers only (`doc.tex` §1). Supports HTTP `Range` requests, so a client "
            "resuming a partial download gets `206 Partial Content` instead of restarting."
        ),
        request=None,
        responses={
            200: OpenApiTypes.BINARY,
            403: Responses.FORBIDDEN_403,
            404: Responses.NOT_FOUND_404,
        },
    )
    def get(self, request, pk):
        track = get_object_or_404(Track, pk=pk)
        if not track.audio_high:
            raise Http404
        filename = track.audio_high.name.rsplit("/", 1)[-1]
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return range_file_response(
            track.audio_high,
            content_type,
            request=request,
            as_attachment=True,
            filename=filename,
        )
