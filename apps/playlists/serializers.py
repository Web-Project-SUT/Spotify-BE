from django.conf import settings
from rest_framework import serializers

from apps.catalog.models import Track
from apps.common.validators import AllowedExtension, MaxFileSize

from .models import Playlist, PlaylistEntry


class PlaylistTrackSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="track_id")
    title = serializers.CharField(source="track.title")
    artist = serializers.UUIDField(source="track.artist_id")
    duration_ms = serializers.IntegerField(source="track.duration_ms")

    class Meta:
        model = PlaylistEntry
        fields = ["id", "title", "artist", "duration_ms", "position"]


class PlaylistListSerializer(serializers.ModelSerializer):
    owner = serializers.UUIDField(source="owner_id", read_only=True)
    track_count = serializers.SerializerMethodField()
    track_ids = serializers.SerializerMethodField()
    last_played_at = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [
            "id",
            "owner",
            "title",
            "is_public",
            "cover",
            "created_at",
            "track_count",
            "track_ids",
            "last_played_at",
        ]

    def get_track_count(self, obj) -> int:
        return len(obj.entries.all())

    # Relies on the queryset's .prefetch_related("entries") — obj.entries.all()
    # then hits the prefetch cache instead of firing one query per playlist.
    def get_track_ids(self, obj) -> list[str]:
        return [str(entry.track_id) for entry in obj.entries.all()]

    # Comes from the queryset annotation, not the model. A method field (not
    # a plain DateTimeField) so serializing an un-annotated Playlist — from a
    # future view, or a single instance — degrades to null instead of raising.
    def get_last_played_at(self, obj) -> str | None:
        played_at = getattr(obj, "last_played_at", None)
        return played_at.isoformat() if played_at else None


class PlaylistSerializer(serializers.ModelSerializer):
    owner = serializers.UUIDField(source="owner_id", read_only=True)
    tracks = PlaylistTrackSerializer(source="entries", many=True, read_only=True)

    class Meta:
        model = Playlist
        fields = ["id", "owner", "title", "is_public", "cover", "created_at", "tracks"]
        read_only_fields = ["id", "owner", "created_at", "tracks"]


class PlaylistWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = ["title", "is_public"]


class AddTrackSerializer(serializers.Serializer):
    track = serializers.PrimaryKeyRelatedField(queryset=Track.objects.all())


class ReorderTracksSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class PlaylistCoverUploadSerializer(serializers.Serializer):
    cover = serializers.ImageField(
        validators=[
            MaxFileSize(settings.MEDIA_IMAGE_MAX_BYTES),
            AllowedExtension(settings.MEDIA_IMAGE_EXTENSIONS),
        ]
    )
