from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Notification, User
from apps.accounts.services import notify

from .models import Track


@receiver(post_save, sender=Track)
def notify_followers_of_new_release(sender, instance, created, **kwargs):
    if not created:
        return
    followers = User.objects.filter(following_edges__following_id=instance.artist_id)
    link = f"/album/{instance.album_id}" if instance.album_id else f"/artist/{instance.artist_id}"
    notify(
        followers,
        type=Notification.Type.RELEASE,
        title="New release",
        message=f'{instance.artist.display_name} just released "{instance.title}".',
        link=link,
    )
