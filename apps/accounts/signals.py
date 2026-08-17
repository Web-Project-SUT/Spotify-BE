from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AccountStatus, ArtistProfile, Role, User
from .services import notify


@receiver(post_save, sender=User)
def ensure_artist_profile(sender, instance, raw=False, **kwargs):
    """Give every artist an `ArtistProfile`, however they became one.

    `register_artist` creates the profile itself, but an admin flipping a
    user's `role` to `artist` in the Django admin does not — and without a
    profile `/api/artists/me/`, the sample-work endpoints and the public
    artist page all break for that user.
    """
    if raw or instance.role != Role.ARTIST:
        return
    ArtistProfile.objects.get_or_create(
        user=instance,
        defaults={"stage_name": instance.display_name or instance.username},
    )


@receiver(post_save, sender=ArtistProfile)
def notify_artist_registration(sender, instance, created, raw=False, **kwargs):
    # Only an application awaiting review is worth pinging reviewers about;
    # a profile backfilled for an admin-promoted (already active) artist is not.
    if raw or not created or instance.user.status != AccountStatus.PENDING:
        return
    recipients = User.objects.filter(role__in=[Role.SUPPORT, Role.ADMIN])
    notify(
        recipients,
        type="approval",
        title="New artist application",
        message=f"{instance.stage_name} has applied to become an artist.",
    )
