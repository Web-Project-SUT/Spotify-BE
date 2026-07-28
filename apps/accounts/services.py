import random
import string

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import AccountStatus, ArtistProfile, Notification, Role, User

_SUFFIX_CHARS = string.digits + string.ascii_lowercase
_MAX_ATTEMPTS = 5


def generate_username(display_name: str) -> str:
    base = slugify(display_name or "user").replace("-", "_") or "user"
    suffix = "".join(random.choices(_SUFFIX_CHARS, k=5))
    return f"{base}_{suffix}"[:48]


def register_listener(
    *, email, password, display_name, birth_date=None, gender="", accepted_policy
):
    for _ in range(_MAX_ATTEMPTS):
        username = generate_username(display_name)
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    email=email,
                    password=password,
                    username=username,
                    display_name=display_name,
                    role=Role.LISTENER,
                    status=AccountStatus.ACTIVE,
                    birth_date=birth_date,
                    gender=gender or "",
                    accepted_policy_at=timezone.now() if accepted_policy else None,
                )
        except IntegrityError:
            continue
    raise RuntimeError("Could not generate a unique username.")


def register_artist(*, email, password, stage_name, portfolio_url=""):
    for _ in range(_MAX_ATTEMPTS):
        username = generate_username(stage_name)
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    username=username,
                    display_name=stage_name,
                    role=Role.ARTIST,
                    status=AccountStatus.PENDING,
                )
                ArtistProfile.objects.create(
                    user=user, stage_name=stage_name, portfolio_url=portfolio_url
                )
                return user
        except IntegrityError:
            continue
    raise RuntimeError("Could not generate a unique username.")


def notify(recipients, *, type, title, message):
    Notification.objects.bulk_create(
        Notification(recipient=recipient, type=type, title=title, message=message)
        for recipient in recipients
    )
