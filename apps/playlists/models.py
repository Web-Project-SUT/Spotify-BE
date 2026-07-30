from django.conf import settings
from django.db import models

from apps.common.media import upload_filename
from apps.common.models import TimeStampedModel, UUIDModel


def playlist_cover_path(instance, filename):
    return f"covers/playlists/{instance.id}/{upload_filename(filename)}"


class Playlist(UUIDModel, TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="playlists"
    )
    title = models.CharField(max_length=120)
    is_public = models.BooleanField(default=False)
    cover = models.ImageField(upload_to=playlist_cover_path, max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        return self.title


class PlaylistEntry(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="entries")
    track = models.ForeignKey(
        "catalog.Track", on_delete=models.CASCADE, related_name="playlist_entries"
    )
    position = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["playlist", "track"], name="uniq_playlist_track"),
            models.UniqueConstraint(
                fields=["playlist", "position"],
                name="uniq_playlist_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]

    def __str__(self):
        return f"{self.playlist_id}#{self.position}"
