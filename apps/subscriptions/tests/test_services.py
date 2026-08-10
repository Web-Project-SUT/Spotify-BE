from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.subscriptions import services

BASE = "https://sandbox.zarinpal.com/pg"


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@override_settings(ZARINPAL_MERCHANT_ID="test-merchant", ZARINPAL_BASE_URL=BASE)
class ZarinpalServiceTests(TestCase):
    @patch("apps.subscriptions.services.requests.post")
    def test_initiate_payment_v4_contract(self, mock_post):
        mock_post.return_value = _Resp({"data": {"code": 100, "authority": "A0001"}, "errors": []})

        authority, url = services.initiate_payment(Decimal("9.99"), "Gold", "http://cb/")

        self.assertEqual(authority, "A0001")
        self.assertEqual(url, f"{BASE}/StartPay/A0001")

        called_url, kwargs = mock_post.call_args
        self.assertEqual(called_url[0], f"{BASE}/v4/payment/request.json")
        body = kwargs["json"]
        self.assertEqual(body["merchant_id"], "test-merchant")
        self.assertEqual(body["amount"], 99900)  # 9.99 * 10000 Rial
        self.assertEqual(body["callback_url"], "http://cb/")

    @patch("apps.subscriptions.services.requests.post")
    def test_initiate_payment_failure_returns_none(self, mock_post):
        mock_post.return_value = _Resp({"data": [], "errors": {"code": -9}})
        self.assertEqual(services.initiate_payment(Decimal("1"), "x", "cb"), (None, None))

    @patch("apps.subscriptions.services.requests.post")
    def test_verify_payment_accepts_100_and_101(self, mock_post):
        for code in (100, 101):
            mock_post.return_value = _Resp({"data": {"code": code, "ref_id": 555}, "errors": []})
            ok, ref = services.verify_payment("A0001", Decimal("9.99"))
            self.assertTrue(ok)
            self.assertEqual(ref, "555")

        called_url, kwargs = mock_post.call_args
        self.assertEqual(called_url[0], f"{BASE}/v4/payment/verify.json")
        self.assertEqual(kwargs["json"]["authority"], "A0001")

    @patch("apps.subscriptions.services.requests.post")
    def test_verify_payment_failure(self, mock_post):
        mock_post.return_value = _Resp({"data": [], "errors": {"code": -51}})
        self.assertEqual(services.verify_payment("A0001", Decimal("9.99")), (False, None))
