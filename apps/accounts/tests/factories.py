import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import AccountStatus, ArtistProfile, Role, User, UserPreferences


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@demo.com")
    username = factory.Sequence(lambda n: f"user_{n}")
    display_name = factory.Faker("first_name")
    role = Role.LISTENER
    status = AccountStatus.ACTIVE

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "password123")
        if create:
            obj.save()


class UserPreferencesFactory(DjangoModelFactory):
    class Meta:
        model = UserPreferences
        django_get_or_create = ("user",)

    user = factory.SubFactory(UserFactory)


class ArtistUserFactory(UserFactory):
    role = Role.ARTIST

    @factory.post_generation
    def artist_profile(obj, create, extracted, **kwargs):
        if not create:
            return
        ArtistProfile.objects.get_or_create(
            user=obj, defaults={"stage_name": obj.display_name or obj.username}
        )
