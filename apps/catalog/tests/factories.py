import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import ArtistUserFactory
from apps.catalog.models import Album, PlayEvent, Track


class AlbumFactory(DjangoModelFactory):
    class Meta:
        model = Album

    artist = factory.SubFactory(ArtistUserFactory)
    title = factory.Faker("sentence", nb_words=3)


class TrackFactory(DjangoModelFactory):
    class Meta:
        model = Track

    artist = factory.SubFactory(ArtistUserFactory)
    title = factory.Faker("sentence", nb_words=2)
    genre = "pop"


class PlayEventFactory(DjangoModelFactory):
    class Meta:
        model = PlayEvent

    user = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    track = factory.SubFactory(TrackFactory)
