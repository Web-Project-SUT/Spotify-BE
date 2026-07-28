from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import ValidationError

from .models import Playlist, PlaylistEntry


def add_track(playlist: Playlist, track) -> PlaylistEntry:
    if playlist.entries.filter(track=track).exists():
        raise ValidationError(
            {"detail": "Track is already in this playlist.", "code": "track_already_added"}
        )
    next_position = (playlist.entries.aggregate(Max("position"))["position__max"] or 0) + 1
    return PlaylistEntry.objects.create(playlist=playlist, track=track, position=next_position)


def reorder_tracks(playlist: Playlist, ordered_track_ids: list) -> None:
    entries = {entry.track_id: entry for entry in playlist.entries.all()}
    if set(entries.keys()) != set(ordered_track_ids):
        raise ValidationError(
            {
                "detail": "The track list must match the playlist's current tracks exactly.",
                "code": "track_list_mismatch",
            }
        )
    with transaction.atomic():
        for position, track_id in enumerate(ordered_track_ids, start=1):
            entries[track_id].position = position
        PlaylistEntry.objects.bulk_update(entries.values(), ["position"])


def remove_track(playlist: Playlist, track_id) -> bool:
    deleted, _ = PlaylistEntry.objects.filter(playlist=playlist, track_id=track_id).delete()
    return bool(deleted)
