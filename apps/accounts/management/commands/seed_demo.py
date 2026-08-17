from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AccountStatus, ArtistProfile, Role, User, UserPreferences
from apps.catalog.models import Album, PlayEvent, Track
from apps.catalog.services import record_stream
from apps.reports.models import PayoutPolicy
from apps.subscriptions.models import Subscription, SubscriptionPlan, Tier, Transaction


class Command(BaseCommand):
    help = "Seeds demo accounts mirroring the frontend's localStorage mock data."

    @transaction.atomic
    def handle(self, *args, **options):
        silver_plan, _ = SubscriptionPlan.objects.get_or_create(
            tier=Tier.SILVER, defaults={"monthly_price": Decimal("4.99")}
        )
        gold_plan, _ = SubscriptionPlan.objects.get_or_create(
            tier=Tier.GOLD, defaults={"monthly_price": Decimal("9.99")}
        )

        self._make_user(
            "listener@demo.com",
            "listener",
            Role.LISTENER,
            preferences={"notif_limit": True, "language": "fa"},
        )
        silver = self._make_user("silver@demo.com", "silver_listener", Role.LISTENER)
        gold = self._make_user("gold@demo.com", "gold_listener", Role.LISTENER)
        nova = self._make_user("nova@demo.com", "nova_ray", Role.ARTIST, display_name="Nova Ray")
        echo = self._make_user(
            "echo@demo.com", "echo_state", Role.ARTIST, display_name="Echo State"
        )
        pending_artist = self._make_user(
            "pending-artist@demo.com",
            "pending_artist",
            Role.ARTIST,
            display_name="Pending Artist",
            status=AccountStatus.PENDING,
        )
        self._make_user("support@demo.com", "support_staff", Role.SUPPORT, is_staff=True)
        self._make_user(
            "admin@demo.com",
            "admin",
            Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        listener = User.objects.get(email="listener@demo.com")

        self._make_subscription(silver, silver_plan)
        self._make_subscription(gold, gold_plan)

        self._make_notifications(gold, nova)
        # listener@demo.com is the most-used demo account; without this its
        # notifications page looks broken (D-14).
        self._make_notifications(listener, nova)

        PayoutPolicy.objects.get_or_create(
            effective_from=date(2020, 1, 1),
            defaults={
                "per_stream_rate": Decimal("0.003"),
                "per_listener_rate": Decimal("0.01"),
            },
        )

        for artist in (nova, echo):
            ArtistProfile.objects.get_or_create(
                user=artist,
                defaults={
                    "stage_name": artist.display_name,
                    "verified_at": timezone.now(),
                },
            )

        ArtistProfile.objects.get_or_create(
            user=pending_artist,
            defaults={"stage_name": pending_artist.display_name},
        )

        nova_tracks = self._seed_catalog(nova)
        self._seed_catalog(echo)

        self._seed_streams(nova_tracks, [listener, silver, gold])

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))

    def _make_user(self, email, username, role, preferences=None, **extra):
        defaults = {
            "username": username,
            "role": role,
            "status": AccountStatus.ACTIVE,
            "is_staff": False,
            "is_superuser": False,
            "accepted_policy_at": timezone.now(),
        }
        defaults.update(extra)
        defaults.setdefault("display_name", username.replace("_", " ").title())
        user, created = User.objects.get_or_create(email=email, defaults=defaults)
        if created:
            user.set_password("password123")
            user.save(update_fields=["password"])
        UserPreferences.objects.get_or_create(user=user, defaults=preferences or {})
        return user

    def _make_subscription(self, user, plan):
        Subscription.objects.get_or_create(
            user=user,
            status="active",
            defaults={
                "plan": plan,
                "period_months": 1,
                "price_paid": plan.monthly_price,
                "starts_at": timezone.now(),
                "expires_at": timezone.now() + timedelta(days=30),
            },
        )
        Transaction.objects.get_or_create(
            user=user,
            plan=plan,
            status=Transaction.Status.SUCCESS,
            defaults={"amount": plan.monthly_price},
        )

    def _seed_catalog(self, artist):
        album, _ = Album.objects.get_or_create(
            artist=artist, title=f"{artist.display_name} - Debut"
        )
        tracks = []
        for i in range(1, 4):
            track, _ = Track.objects.get_or_create(
                artist=artist,
                album=album,
                title=f"{artist.display_name} Track {i}",
                defaults={"genre": "pop", "duration_ms": 180_000},
            )
            tracks.append(track)
        return tracks

    def _seed_streams(self, tracks, listeners):
        for track in tracks:
            for listener in listeners:
                if not PlayEvent.objects.filter(user=listener, track=track).exists():
                    record_stream(user=listener, track=track)

    def _make_notifications(self, listener, artist):
        from apps.accounts.models import Notification

        specs = [
            (listener, "Welcome to Streamr", "Enjoy unlimited listening.", "subscription"),
            (listener, "New release", "An artist you follow just dropped a track.", "release"),
            (artist, "Profile approved", "Your artist account is now active.", "approval"),
        ]
        for recipient, title, message, ntype in specs:
            Notification.objects.get_or_create(
                recipient=recipient, title=title, defaults={"message": message, "type": ntype}
            )
