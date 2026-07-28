from django.db.models import F

from .models import PlayEvent, Track


def record_stream(*, user, track, playlist=None):
    is_first_listen = not PlayEvent.objects.filter(user=user, track=track).exists()
    event = PlayEvent.objects.create(user=user, track=track, playlist=playlist)
    Track.objects.filter(pk=track.pk).update(play_count=F("play_count") + 1)
    if is_first_listen:
        Track.objects.filter(pk=track.pk).update(
            unique_listener_count=F("unique_listener_count") + 1
        )
    return event
