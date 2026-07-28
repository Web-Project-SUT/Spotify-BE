import mimetypes

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.http import range_file_response
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


@extend_schema_view(
    put=extend_schema(
        request={"multipart/form-data": AlbumCoverUploadSerializer},
        responses={200: AlbumDetailSerializer},
    ),
    delete=extend_schema(responses={204: None}),
)
class AlbumCoverView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated, IsArtistOwner]
    queryset = Album.objects.all()
    media_fields = ("cover",)
    upload_serializer_class = AlbumCoverUploadSerializer
    read_serializer_class = AlbumDetailSerializer


@extend_schema_view(
    put=extend_schema(
        request={"multipart/form-data": TrackCoverUploadSerializer},
        responses={200: TrackListSerializer},
    ),
    delete=extend_schema(responses={204: None}),
)
class TrackCoverView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated, IsArtistOwner]
    queryset = Track.objects.all()
    media_fields = ("cover",)
    upload_serializer_class = TrackCoverUploadSerializer
    read_serializer_class = TrackListSerializer


@extend_schema_view(
    put=extend_schema(
        request={"multipart/form-data": TrackAudioUploadSerializer},
        responses={200: TrackListSerializer},
    ),
    delete=extend_schema(responses={204: None}),
)
class TrackAudioView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated, IsApprovedArtist, IsArtistOwner]
    queryset = Track.objects.all()
    media_fields = ("audio_high", "audio_low")
    upload_serializer_class = TrackAudioUploadSerializer
    read_serializer_class = TrackListSerializer


class TrackDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSilverOrAbove]

    @extend_schema(request=None, responses={200: OpenApiTypes.BINARY})
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
