from django.db import IntegrityError, connection, transaction
from rest_framework.test import APITestCase

from apps.catalog.tests.factories import TrackFactory
from apps.playlists.models import PlaylistEntry
from apps.playlists.tests.factories import PlaylistFactory


class PlaylistEntryModelTests(APITestCase):
    def test_track_uniqueness_within_playlist(self):
        playlist = PlaylistFactory()
        track = TrackFactory()
        PlaylistEntry.objects.create(playlist=playlist, track=track, position=1)
        with self.assertRaises(IntegrityError):
            PlaylistEntry.objects.create(playlist=playlist, track=track, position=2)

    def test_position_uniqueness_within_playlist(self):
        # uniq_playlist_position is DEFERRABLE DEFERRED (to allow reordering in
        # one transaction), so it's only checked at commit — force the check.
        playlist = PlaylistFactory()
        PlaylistEntry.objects.create(playlist=playlist, track=TrackFactory(), position=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlaylistEntry.objects.create(playlist=playlist, track=TrackFactory(), position=1)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS uniq_playlist_position IMMEDIATE")
