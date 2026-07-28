from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from apps.common.media import upload_filename
from apps.common.models import TimeStampedModel, UUIDModel


class ReleaseType(models.TextChoices):
    SINGLE = "single", "Single"
    ALBUM_TRACK = "album_track", "Album track"


def album_cover_path(instance, filename):
    return f"covers/albums/{instance.id}/{upload_filename(filename)}"


def track_cover_path(instance, filename):
    return f"covers/tracks/{instance.id}/{upload_filename(filename)}"


def track_audio_path(instance, filename):
    return f"audio/{instance.artist_id}/{instance.id}/{upload_filename(filename)}"


class Album(UUIDModel, TimeStampedModel):
    artist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="albums"
    )
    title = models.CharField(max_length=120, db_index=True)
    cover = models.ImageField(upload_to=album_cover_path, max_length=255, null=True, blank=True)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    released_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-released_at"]
        indexes = [models.Index(fields=["artist", "-released_at"])]

    def __str__(self):
        return self.title


class Track(UUIDModel, TimeStampedModel):
    artist = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracks"
    )
    album = models.ForeignKey(
        Album,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tracks",
    )
    title = models.CharField(max_length=120, db_index=True)
    cover = models.ImageField(upload_to=track_cover_path, max_length=255, null=True, blank=True)
    lyrics = models.TextField(blank=True)
    genre = models.CharField(max_length=40, blank=True, db_index=True)
    release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    released_at = models.DateTimeField(default=timezone.now, db_index=True)
    release_type = models.CharField(
        max_length=16, choices=ReleaseType.choices, default=ReleaseType.SINGLE
    )
    collaborators = ArrayField(models.CharField(max_length=80), default=list, blank=True)
    audio_high = models.FileField(upload_to=track_audio_path, max_length=255, null=True, blank=True)
    audio_low = models.FileField(upload_to=track_audio_path, max_length=255, null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    early_access_until = models.DateTimeField(null=True, blank=True)
    play_count = models.PositiveIntegerField(default=0, db_index=True)
    unique_listener_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-released_at"]
        indexes = [
            models.Index(fields=["artist", "-released_at"]),
            models.Index(fields=["genre"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.album_id and self.album.artist_id != self.artist_id:
            raise ValidationError("Track artist must match its album's artist.")


class PlayEvent(UUIDModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="play_events"
    )
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="play_events")
    playlist = models.ForeignKey(
        "playlists.Playlist",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="play_events",
    )
    played_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-played_at"]),
            models.Index(fields=["track", "-played_at"]),
            models.Index(fields=["user", "track"]),
        ]
