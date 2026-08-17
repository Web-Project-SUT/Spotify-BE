from django.db.models import F, Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.quotas import PlaylistQuota
from apps.common.views import MediaResourceView

from . import services
from .models import Playlist
from .permissions import IsPlaylistOwner
from .serializers import (
    AddTrackSerializer,
    PlaylistCoverUploadSerializer,
    PlaylistListSerializer,
    PlaylistSerializer,
    PlaylistTrackSerializer,
    PlaylistWriteSerializer,
    ReorderTracksSerializer,
)


class PlaylistViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Playlist.objects.none()
        if self.action == "list":
            # order_by is explicit because annotate() with an aggregate drops
            # Meta.ordering (it would otherwise land in the GROUP BY), which
            # leaves the paginator with an unordered queryset.
            return (
                Playlist.objects.filter(owner=self.request.user)
                .annotate(last_played_at=Max("play_events__played_at"))
                .prefetch_related("entries")
                .order_by("-created_at")
            )
        # Object-level permission (IsPlaylistOwner) enforces public-vs-owner
        # access; a private playlist owned by someone else should 403, not
        # be silently excluded from the queryset and read as a 404.
        return Playlist.objects.all().prefetch_related("entries__track")

    def get_serializer_class(self):
        if self.action == "list":
            return PlaylistListSerializer
        if self.action in ("create", "update", "partial_update"):
            return PlaylistWriteSerializer
        return PlaylistSerializer

    def get_permissions(self):
        if self.action in ("retrieve", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsPlaylistOwner()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        PlaylistQuota().check(self.request.user)
        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = PlaylistSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output = PlaylistSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=False, methods=["get"], url_path="recent")
    def recent(self, request):
        queryset = (
            Playlist.objects.filter(owner=request.user)
            .annotate(last_played_at=Max("play_events__played_at"))
            .prefetch_related("entries")
            .order_by(F("last_played_at").desc(nulls_last=True))
        )
        page = self.paginate_queryset(queryset)
        serializer = PlaylistListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)


class PlaylistTracksView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_playlist(self, playlist_id):
        return get_object_or_404(Playlist, pk=playlist_id, owner=self.request.user)

    @extend_schema(request=AddTrackSerializer, responses={201: PlaylistTrackSerializer})
    def post(self, request, playlist_id):
        playlist = self.get_playlist(playlist_id)
        serializer = AddTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.add_track(playlist, serializer.validated_data["track"])
        return Response(PlaylistTrackSerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReorderTracksSerializer, responses={200: PlaylistSerializer})
    def put(self, request, playlist_id):
        playlist = self.get_playlist(playlist_id)
        serializer = ReorderTracksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reorder_tracks(playlist, serializer.validated_data["order"])
        playlist.refresh_from_db()
        return Response(PlaylistSerializer(playlist, context={"request": request}).data)


class PlaylistTrackDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request, playlist_id, track_id):
        playlist = get_object_or_404(Playlist, pk=playlist_id, owner=request.user)
        if not services.remove_track(playlist, track_id):
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    put=extend_schema(
        request={"multipart/form-data": PlaylistCoverUploadSerializer},
        responses={200: PlaylistSerializer},
    ),
    delete=extend_schema(responses={204: None}),
)
class PlaylistCoverView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated, IsPlaylistOwner]
    queryset = Playlist.objects.all()
    media_fields = ("cover",)
    upload_serializer_class = PlaylistCoverUploadSerializer
    read_serializer_class = PlaylistSerializer
