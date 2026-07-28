from rest_framework import serializers

from apps.catalog.models import Track

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

    class Meta:
        model = Playlist
        fields = ["id", "owner", "title", "is_public", "created_at", "track_count"]

    def get_track_count(self, obj) -> int:
        return obj.entries.count()


class PlaylistSerializer(serializers.ModelSerializer):
    owner = serializers.UUIDField(source="owner_id", read_only=True)
    tracks = PlaylistTrackSerializer(source="entries", many=True, read_only=True)

    class Meta:
        model = Playlist
        fields = ["id", "owner", "title", "is_public", "created_at", "tracks"]
        read_only_fields = ["id", "owner", "created_at", "tracks"]


class PlaylistWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = ["title", "is_public"]


class AddTrackSerializer(serializers.Serializer):
    track = serializers.PrimaryKeyRelatedField(queryset=Track.objects.all())


class ReorderTracksSerializer(serializers.Serializer):
    order = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
