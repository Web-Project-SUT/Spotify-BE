import random
import string

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import AccountStatus, ArtistProfile, Notification, Role, User, UserPreferences

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
                user = User.objects.create_user(
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
                get_preferences(user)
                return user
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
                # `ensure_artist_profile` has already created the row from the
                # `User` post_save, so fill in the application details rather
                # than inserting a second time.
                ArtistProfile.objects.update_or_create(
                    user=user,
                    defaults={"stage_name": stage_name, "portfolio_url": portfolio_url},
                )
                get_preferences(user)
                return user
        except IntegrityError:
            continue
    raise RuntimeError("Could not generate a unique username.")


def create_user(
    *, email, password, display_name="", role=Role.LISTENER, status=AccountStatus.ACTIVE
):
    """Create a user on an admin's behalf (the dashboard's Users tab).

    Unlike self-registration there is no approval step: whatever role and
    status the admin picked is what the account gets.
    """
    for _ in range(_MAX_ATTEMPTS):
        username = generate_username(display_name or email.split("@")[0])
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    username=username,
                    display_name=display_name,
                    role=role,
                    status=status,
                )
                get_preferences(user)
                return user
        except IntegrityError:
            continue
    raise RuntimeError("Could not generate a unique username.")


def get_preferences(user):
    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


# `release` is the only suppressible notification type: `subscription` is
# money/access, `approval` is the only way a pending artist learns their
# application was decided, and `support` is the reply to a ticket the
# recipient opened themselves — suppressing any of those is user-hostile.
# `release` is a "someone you follow put something out" ping, which is
# exactly the kind of notification a volume control should be able to mute.
SUPPRESSIBLE_NOTIFICATION_TYPES = frozenset({Notification.Type.RELEASE})


def notify(recipients, *, type, title, message, link=""):
    recipients = list(recipients)
    if type in SUPPRESSIBLE_NOTIFICATION_TYPES:
        limited = set(
            UserPreferences.objects.filter(
                user_id__in=[recipient.pk for recipient in recipients], notif_limit=True
            ).values_list("user_id", flat=True)
        )
        recipients = [recipient for recipient in recipients if recipient.pk not in limited]
    Notification.objects.bulk_create(
        Notification(recipient=recipient, type=type, title=title, message=message, link=link)
        for recipient in recipients
    )
