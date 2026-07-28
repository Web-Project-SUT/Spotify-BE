import factory
from factory.django import DjangoModelFactory

from apps.playlists.models import Playlist, PlaylistEntry


class PlaylistFactory(DjangoModelFactory):
    class Meta:
        model = Playlist

    owner = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    title = factory.Faker("sentence", nb_words=2)


class PlaylistEntryFactory(DjangoModelFactory):
    class Meta:
        model = PlaylistEntry

    playlist = factory.SubFactory(PlaylistFactory)
    track = factory.SubFactory("apps.catalog.tests.factories.TrackFactory")
    position = factory.Sequence(lambda n: n)
