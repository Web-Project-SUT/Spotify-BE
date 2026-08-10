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
import requests
from django.conf import settings

REQUEST_TIMEOUT = 10


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
    except (requests.RequestException, ValueError):
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
    except (requests.RequestException, ValueError):
        pass
    return False, None
