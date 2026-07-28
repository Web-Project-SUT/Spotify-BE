from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ArtistProfile, Role, User
from .services import notify


@receiver(post_save, sender=ArtistProfile)
def notify_artist_registration(sender, instance, created, **kwargs):
    if not created:
        return
    recipients = User.objects.filter(role__in=[Role.SUPPORT, Role.ADMIN])
    notify(
        recipients,
        type="approval",
        title="New artist application",
        message=f"{instance.stage_name} has applied to become an artist.",
    )
