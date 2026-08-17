from django.core.management.base import BaseCommand

from apps.subscriptions import services


class Command(BaseCommand):
    help = (
        "Flips lapsed subscriptions to EXPIRED and sends an expiry-warning "
        "notification for ones expiring soon."
    )

    def handle(self, *args, **options):
        result = services.expire_subscriptions()
        self.stdout.write(
            self.style.SUCCESS(f"expired={result['expired']} warned={result['warned']}")
        )
