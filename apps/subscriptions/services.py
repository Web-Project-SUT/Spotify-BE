"""Zarinpal payment gateway integration (v4 REST API).

The gateway is called twice per purchase:

  1. request  -> POST {base}/v4/payment/request.json  with
     {merchant_id, amount, description, callback_url}. On success the
     response carries data.code == 100 and data.authority; the user is then
     sent to {base}/StartPay/{authority} to pay.
  2. verify   -> POST {base}/v4/payment/verify.json    with
     {merchant_id, amount, authority} after Zarinpal calls our callback.
     data.code 100 (verified) or 101 (already verified) means success.

Both merchant_id and the base URL come from settings so the same code runs
against the sandbox in development and the live gateway in production.
`amount` is sent in Rial (the stored monthly price is scaled by 10000).
"""

import calendar
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.exceptions import APIException

from apps.accounts.models import Notification
from apps.accounts.services import notify

from .models import Subscription

REQUEST_TIMEOUT = 10
EXPIRY_WARNING_DAYS = 3


class PaymentGatewayError(APIException):
    status_code = http_status.HTTP_502_BAD_GATEWAY
    default_detail = "Payment gateway error."
    default_code = "payment_gateway_error"


def _base() -> str:
    return settings.ZARINPAL_BASE_URL.rstrip("/")


def _to_rial(amount) -> int:
    return int(amount * 10000)


def initiate_payment(amount, description, callback_url):
    """Create a payment and return (authority, start_pay_url) or (None, None)."""
    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": _to_rial(amount),
        "description": description,
        "callback_url": callback_url,
    }
    try:
        response = requests.post(
            f"{_base()}/v4/payment/request.json", json=payload, timeout=REQUEST_TIMEOUT
        )
        data = (response.json() or {}).get("data") or {}
        if data.get("code") == 100 and data.get("authority"):
            authority = data["authority"]
            return authority, f"{_base()}/StartPay/{authority}"
    except (requests.RequestException, ValueError):  # fmt: skip
        pass
    return None, None


def verify_payment(authority, amount):
    """Verify a returned payment and return (is_verified, ref_id)."""
    payload = {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": _to_rial(amount),
        "authority": authority,
    }
    try:
        response = requests.post(
            f"{_base()}/v4/payment/verify.json", json=payload, timeout=REQUEST_TIMEOUT
        )
        data = (response.json() or {}).get("data") or {}
        # 100 = verified now, 101 = previously verified (idempotent replay).
        if data.get("code") in (100, 101):
            return True, str(data.get("ref_id"))
    except (requests.RequestException, ValueError):  # fmt: skip
        pass
    return False, None


def add_months(dt, months):
    """Add calendar months to a datetime, clamping the day when the target
    month is shorter (e.g. Jan 31 + 1 month -> Feb 28/29)."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def activate_subscription(transaction):
    """Renew-or-create the user's subscription for a successfully paid
    transaction, in one atomic step.

    Renewing while the user still has an active subscription extends from
    its current expiry rather than from now, so they don't lose time they
    already paid for. The old row has to flip to EXPIRED *before* the new
    row is inserted — `one_active_subscription` is a partial unique
    constraint on status="active", so both can't hold that status at once,
    even momentarily within the same transaction.
    """
    now = timezone.now()
    with db_transaction.atomic():
        current = Subscription.objects.filter(
            user=transaction.user, status=Subscription.Status.ACTIVE
        ).first()
        starts_at = current.expires_at if current and current.expires_at > now else now
        expires_at = add_months(starts_at, transaction.period_months)

        if current is not None:
            current.status = Subscription.Status.EXPIRED
            current.save(update_fields=["status"])

        return Subscription.objects.create(
            user=transaction.user,
            plan=transaction.plan,
            period_months=transaction.period_months,
            price_paid=transaction.amount,
            starts_at=starts_at,
            expires_at=expires_at,
            status=Subscription.Status.ACTIVE,
        )


def expire_subscriptions(*, now=None):
    """Flip lapsed subscriptions to EXPIRED and warn users whose active
    subscription expires within EXPIRY_WARNING_DAYS.

    Meant to run periodically (mirrors generate_payouts). `User.tier` reads
    `expires_at` directly, so a lapsed row losing its listener-facing effect
    doesn't depend on this running — but Status.EXPIRED itself, and the
    warning, do.
    """
    now = now or timezone.now()
    expired = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, expires_at__lte=now
    ).update(status=Subscription.Status.EXPIRED)

    warning_cutoff = now + timedelta(days=EXPIRY_WARNING_DAYS)
    expiring_soon = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, expires_at__gt=now, expires_at__lte=warning_cutoff
    ).select_related("user", "plan")

    warned = 0
    for sub in expiring_soon:
        # Scoped to this subscription's own period (created_at >= starts_at)
        # so a renewal starts a fresh warning rather than being silenced by
        # one sent for the subscription it replaced.
        already_warned = Notification.objects.filter(
            recipient=sub.user,
            type=Notification.Type.SUBSCRIPTION,
            title="Your subscription is expiring soon",
            created_at__gte=sub.starts_at,
        ).exists()
        if already_warned:
            continue
        notify(
            [sub.user],
            type=Notification.Type.SUBSCRIPTION,
            title="Your subscription is expiring soon",
            message=(
                f"Your {sub.plan.tier} subscription expires on "
                f"{sub.expires_at:%Y-%m-%d}. Renew to keep your benefits."
            ),
            link="/upgrade",
        )
        warned += 1

    return {"expired": expired, "warned": warned}
