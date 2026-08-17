from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.subscriptions import services
from apps.subscriptions.models import Subscription, Transaction
from apps.subscriptions.tests.factories import SubscriptionFactory, SubscriptionPlanFactory

BASE = "https://sandbox.zarinpal.com/pg"


class AddMonthsTests(TestCase):
    def test_adds_whole_months(self):
        start = timezone.make_aware(datetime(2026, 1, 15, 10, 0))
        expected = timezone.make_aware(datetime(2026, 4, 15, 10, 0))
        self.assertEqual(services.add_months(start, 3), expected)

    def test_rolls_over_the_year(self):
        start = timezone.make_aware(datetime(2026, 11, 1))
        self.assertEqual(services.add_months(start, 3), timezone.make_aware(datetime(2027, 2, 1)))

    def test_clamps_the_day_for_a_shorter_month(self):
        start = timezone.make_aware(datetime(2026, 1, 31))
        self.assertEqual(services.add_months(start, 1), timezone.make_aware(datetime(2026, 2, 28)))


class ActivateSubscriptionTests(TestCase):
    def test_creates_a_fresh_subscription_when_none_exists(self):
        plan = SubscriptionPlanFactory()
        user = UserFactory()
        transaction = Transaction.objects.create(
            user=user, plan=plan, period_months=1, amount=plan.monthly_price
        )

        sub = services.activate_subscription(transaction)

        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.period_months, 1)

    def test_extends_from_current_expiry_when_still_active(self):
        plan = SubscriptionPlanFactory()
        future_expiry = timezone.now() + timezone.timedelta(days=10)
        existing = SubscriptionFactory(
            plan=plan, status=Subscription.Status.ACTIVE, expires_at=future_expiry
        )
        transaction = Transaction.objects.create(
            user=existing.user, plan=plan, period_months=1, amount=plan.monthly_price
        )

        new_sub = services.activate_subscription(transaction)

        self.assertEqual(new_sub.starts_at, future_expiry)
        existing.refresh_from_db()
        self.assertEqual(existing.status, Subscription.Status.EXPIRED)

    def test_starts_from_now_when_the_prior_subscription_already_lapsed(self):
        plan = SubscriptionPlanFactory()
        user = UserFactory()
        past_expiry = timezone.now() - timezone.timedelta(days=5)
        SubscriptionFactory(
            user=user, plan=plan, status=Subscription.Status.EXPIRED, expires_at=past_expiry
        )
        transaction = Transaction.objects.create(
            user=user, plan=plan, period_months=1, amount=plan.monthly_price
        )

        new_sub = services.activate_subscription(transaction)
        self.assertGreater(new_sub.starts_at, past_expiry)


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
