from django.conf import settings
from rest_framework import serializers

from apps.common.validators import AllowedExtension, AudioSignature, MaxFileSize
from apps.playlists.models import Playlist

from . import services
from .models import Album, PlayEvent, Track


class TrackListSerializer(serializers.ModelSerializer):
    artist = serializers.UUIDField(source="artist_id", read_only=True)
    album = serializers.UUIDField(source="album_id", read_only=True, allow_null=True)
    # doc.tex restricts listener/stream counts to gold; enforce it server-side
    # (D-1) rather than trusting the frontend to hide them. The track's own
    # artist and staff always see them (artist dashboard, moderation).
    play_count = serializers.SerializerMethodField()
    unique_listener_count = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            "id",
            "artist",
            "album",
            "title",
            "lyrics",
            "genre",
            "release_year",
            "released_at",
            "release_type",
            "collaborators",
            "duration_ms",
            "play_count",
            "unique_listener_count",
            "early_access_until",
            "cover",
            "audio_high",
            "audio_low",
        ]
        read_only_fields = ["id", "artist", "play_count", "unique_listener_count"]

    def _may_see_stats(self, instance) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return user.tier == "gold" or user.is_staff or instance.artist_id == user.id

    def get_play_count(self, instance):
        return instance.play_count if self._may_see_stats(instance) else None

    def get_unique_listener_count(self, instance):
        return instance.unique_listener_count if self._may_see_stats(instance) else None


class AlbumListSerializer(serializers.ModelSerializer):
    artist = serializers.UUIDField(source="artist_id", read_only=True)

    class Meta:
        model = Album
        fields = ["id", "artist", "title", "release_year", "released_at", "created_at", "cover"]
        read_only_fields = ["id", "artist", "created_at"]


class AlbumDetailSerializer(AlbumListSerializer):
    tracks = TrackListSerializer(many=True, read_only=True)

    class Meta(AlbumListSerializer.Meta):
        fields = AlbumListSerializer.Meta.fields + ["tracks"]


class AlbumWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = ["title", "release_year", "released_at"]


class TrackWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = [
            "album",
            "title",
            "lyrics",
            "genre",
            "release_year",
            "release_type",
            "collaborators",
            "duration_ms",
            "early_access_until",
        ]

    def validate_album(self, album):
        request = self.context["request"]
        if album is not None and album.artist_id != request.user.id:
            raise serializers.ValidationError("Album must belong to you.")
        return album


class StreamCreateSerializer(serializers.Serializer):
    track = serializers.PrimaryKeyRelatedField(queryset=Track.objects.all())
    playlist = serializers.PrimaryKeyRelatedField(
        queryset=Playlist.objects.all(), required=False, allow_null=True
    )

    def create(self, validated_data):
        return services.record_stream(user=self.context["request"].user, **validated_data)


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayEvent
        fields = ["id", "track", "playlist", "played_at"]
        read_only_fields = fields


class AlbumCoverUploadSerializer(serializers.Serializer):
    cover = serializers.ImageField(
        validators=[
            MaxFileSize(settings.MEDIA_IMAGE_MAX_BYTES),
            AllowedExtension(settings.MEDIA_IMAGE_EXTENSIONS),
        ]
    )


class TrackCoverUploadSerializer(serializers.Serializer):
    cover = serializers.ImageField(
        validators=[
            MaxFileSize(settings.MEDIA_IMAGE_MAX_BYTES),
            AllowedExtension(settings.MEDIA_IMAGE_EXTENSIONS),
        ]
    )


class TrackAudioUploadSerializer(serializers.Serializer):
    audio_high = serializers.FileField(
        required=True,
        validators=[
            MaxFileSize(settings.MEDIA_AUDIO_MAX_BYTES),
            AllowedExtension(settings.MEDIA_AUDIO_EXTENSIONS),
            AudioSignature(),
        ],
    )
    # Optional: the low-quality transcode. Artists upload one file; requiring
    # both here 400s every real upload and leaves the track row silent.
    audio_low = serializers.FileField(
        required=False,
        validators=[
            MaxFileSize(settings.MEDIA_AUDIO_MAX_BYTES),
            AllowedExtension(settings.MEDIA_AUDIO_EXTENSIONS),
            AudioSignature(),
        ],
    )
