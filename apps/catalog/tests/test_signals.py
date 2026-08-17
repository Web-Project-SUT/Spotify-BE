from django.test import TestCase

from apps.accounts.models import Follow, Notification
from apps.accounts.tests.factories import ArtistUserFactory, UserFactory
from apps.catalog.models import ReleaseType
from apps.catalog.tests.factories import AlbumFactory, TrackFactory


class NewReleaseNotificationTests(TestCase):
    def test_creating_a_track_notifies_followers_with_a_link(self):
        artist = ArtistUserFactory()
        follower = UserFactory()
        Follow.objects.create(follower=follower, following=artist)

        TrackFactory(artist=artist, title="Neon Skyline")

        notification = Notification.objects.get(recipient=follower)
        self.assertEqual(notification.type, "release")
        self.assertIn("Neon Skyline", notification.message)
        self.assertEqual(notification.link, f"/artist/{artist.id}")

    def test_album_track_links_to_the_album(self):
        artist = ArtistUserFactory()
        follower = UserFactory()
        Follow.objects.create(follower=follower, following=artist)
        album = AlbumFactory(artist=artist)

        TrackFactory(artist=artist, album=album, release_type=ReleaseType.ALBUM_TRACK)

        notification = Notification.objects.get(recipient=follower)
        self.assertEqual(notification.link, f"/album/{album.id}")

    def test_non_followers_are_not_notified(self):
        artist = ArtistUserFactory()
        UserFactory()  # unrelated user, does not follow

        TrackFactory(artist=artist)

        self.assertFalse(Notification.objects.exists())

    def test_updating_a_track_does_not_renotify(self):
        artist = ArtistUserFactory()
        follower = UserFactory()
        Follow.objects.create(follower=follower, following=artist)
        track = TrackFactory(artist=artist)
        Notification.objects.all().delete()

        track.title = "Renamed"
        track.save()

        self.assertFalse(Notification.objects.exists())
