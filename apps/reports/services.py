from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Notification, User
from apps.accounts.services import notify
from apps.catalog.models import Album, PlayEvent, Track
from apps.common.quotas import DailyStreamQuota
from apps.subscriptions.models import Subscription, Transaction

from .models import ArtistPayout, PayoutPolicy


def previous_month(today: date | None = None) -> date:
    today = today or timezone.now().date()
    first_of_this_month = date(today.year, today.month, 1)
    if first_of_this_month.month == 1:
        return date(first_of_this_month.year - 1, 12, 1)
    return date(first_of_this_month.year, first_of_this_month.month - 1, 1)


def month_bounds(period: date) -> tuple[datetime, datetime]:
    start = timezone.make_aware(datetime(period.year, period.month, 1))
    if period.month == 12:
        end = timezone.make_aware(datetime(period.year + 1, 1, 1))
    else:
        end = timezone.make_aware(datetime(period.year, period.month + 1, 1))
    return start, end


def parse_period(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        year_str, month_str = value.split("-")
        return date(int(year_str), int(month_str), 1)
    except (ValueError, AttributeError) as exc:
        raise ValidationError({"period": "Expected format YYYY-MM."}) from exc


_EARNINGS_FIELD = DecimalField(max_digits=14, decimal_places=6)


def track_stats(*, artist, since=None, until=None, policy=None):
    window = Q()
    if since is not None:
        window &= Q(play_events__played_at__gte=since)
    if until is not None:
        window &= Q(play_events__played_at__lt=until)
    queryset = Track.objects.filter(artist=artist).annotate(
        streams=Count("play_events", filter=window),
        listeners=Count("play_events__user", distinct=True, filter=window),
    )
    if policy is not None:
        earnings_expr = ExpressionWrapper(
            F("streams") * policy.per_stream_rate + F("listeners") * policy.per_listener_rate,
            output_field=_EARNINGS_FIELD,
        )
    else:
        earnings_expr = Value(Decimal("0"), output_field=_EARNINGS_FIELD)
    return queryset.annotate(earnings=earnings_expr)


def artist_summary(*, artist, since=None, until=None) -> dict:
    window = Q(track__artist=artist)
    if since is not None:
        window &= Q(played_at__gte=since)
    if until is not None:
        window &= Q(played_at__lt=until)
    agg = PlayEvent.objects.filter(window).aggregate(
        streams=Count("id"), listeners=Count("user", distinct=True)
    )
    streams = agg["streams"] or 0
    listeners = agg["listeners"] or 0

    policy = PayoutPolicy.for_period(since.date() if since is not None else timezone.now().date())
    earnings = (
        streams * policy.per_stream_rate + listeners * policy.per_listener_rate
        if policy
        else Decimal("0")
    )

    top = track_stats(artist=artist, since=since, until=until).order_by("-streams").first()
    top_track = None
    if top is not None and top.streams:
        top_track = {"id": top.id, "title": top.title, "streams": top.streams}

    return {
        "streams": streams,
        "listeners": listeners,
        "earnings": earnings,
        "top_track": top_track,
    }


def build_monthly_payouts(*, period: date) -> dict:
    since, until = month_bounds(period)
    policy = PayoutPolicy.for_period(period)
    rows = (
        PlayEvent.objects.filter(played_at__gte=since, played_at__lt=until)
        .values("track__artist")
        .annotate(streams=Count("id"), listeners=Count("user", distinct=True))
    )

    created = updated = skipped_settled = 0
    touched_artist_ids = []
    with transaction.atomic():
        for row in rows:
            existing = ArtistPayout.objects.filter(
                artist_id=row["track__artist"], period_month=period
            ).first()
            if existing is not None and existing.status == ArtistPayout.Status.PAID:
                skipped_settled += 1
                continue

            amount = (
                row["streams"] * policy.per_stream_rate
                + row["listeners"] * policy.per_listener_rate
                if policy
                else Decimal("0")
            )
            _, was_created = ArtistPayout.objects.update_or_create(
                artist_id=row["track__artist"],
                period_month=period,
                defaults={
                    "unique_listeners": row["listeners"],
                    "streams": row["streams"],
                    "amount": amount,
                    "policy": policy,
                },
            )
            touched_artist_ids.append(row["track__artist"])
            if was_created:
                created += 1
            else:
                updated += 1

    # Outside the transaction: a notification failure shouldn't roll back
    # payout rows that were successfully computed.
    if touched_artist_ids:
        notify(
            User.objects.filter(id__in=touched_artist_ids),
            type=Notification.Type.SUBSCRIPTION,
            title="Monthly earnings calculated",
            message=f"Your payout for {period:%B %Y} has been calculated.",
            link="/artist-panel",
        )

    return {
        "period": period,
        "created": created,
        "updated": updated,
        "skipped_settled": skipped_settled,
    }


def revenue_series(*, months: int) -> list[dict]:
    now = timezone.now()
    current_month = date(now.year, now.month, 1)

    month_list = []
    year, month = current_month.year, current_month.month
    for _ in range(months):
        month_list.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    month_list.reverse()

    since, _ = month_bounds(month_list[0])
    totals = (
        Transaction.objects.filter(status="success", created_at__gte=since)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(total=Sum("amount"))
    )
    totals_by_month = {row["m"].date(): row["total"] for row in totals}

    return [
        {
            "month": month_date.strftime("%Y-%m"),
            "label": month_date.strftime("%b"),
            "amount": totals_by_month.get(month_date) or Decimal("0"),
        }
        for month_date in month_list
    ]


def revenue_summary() -> dict:
    now = timezone.now()
    since, until = month_bounds(date(now.year, now.month, 1))
    current_month = Transaction.objects.filter(
        status="success", created_at__gte=since, created_at__lt=until
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total = Transaction.objects.filter(status="success").aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0")
    active_subscriptions = Subscription.objects.filter(status="active", expires_at__gt=now).count()
    return {
        "current_month": current_month,
        "total": total,
        "active_subscriptions": active_subscriptions,
    }


def tier_distribution() -> dict:
    now = timezone.now()
    total_listeners = User.objects.filter(role="listener").count()
    tier_counts = (
        Subscription.objects.filter(status="active", expires_at__gt=now, user__role="listener")
        .values("plan__tier")
        .annotate(count=Count("user", distinct=True))
    )
    counts = {row["plan__tier"]: row["count"] for row in tier_counts}
    silver = counts.get("silver", 0)
    gold = counts.get("gold", 0)
    return {"basic": total_listeners - silver - gold, "silver": silver, "gold": gold}


def platform_totals() -> dict:
    now = timezone.now()
    since, until = month_bounds(date(now.year, now.month, 1))
    return {
        "users": User.objects.count(),
        "listeners": User.objects.filter(role="listener").count(),
        "artists": User.objects.filter(role="artist", status="active").count(),
        "pending_artists": User.objects.filter(role="artist", status="pending").count(),
        "tracks": Track.objects.count(),
        "albums": Album.objects.count(),
        "streams_this_month": PlayEvent.objects.filter(
            played_at__gte=since, played_at__lt=until
        ).count(),
    }


def listening_stats(*, user) -> dict:
    quota = DailyStreamQuota()
    today = timezone.now().date()
    since, until = month_bounds(date(today.year, today.month, 1))

    streams_today = quota.current_count(user)
    streams_this_month = PlayEvent.objects.filter(
        user=user, played_at__gte=since, played_at__lt=until
    ).count()
    daily_limit = quota.limit_for(user.tier)
    remaining_today = None if daily_limit is None else max(daily_limit - streams_today, 0)

    return {
        "streams_today": streams_today,
        "streams_this_month": streams_this_month,
        "daily_limit": daily_limit,
        "remaining_today": remaining_today,
    }
