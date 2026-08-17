from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.subscriptions.models import Subscription, SubscriptionPlan, Tier, Transaction
from apps.subscriptions.tests.factories import SubscriptionFactory

User = get_user_model()

FE = "http://localhost:3000"


@override_settings(FRONTEND_URL=FE)
class PaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", username="testuser", password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.plan = SubscriptionPlan.objects.create(tier=Tier.GOLD, monthly_price=Decimal("9.99"))

    def test_plan_list_is_public(self):
        client = APIClient()  # unauthenticated
        response = client.get(reverse("plan-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tiers = [p["tier"] for p in response.data]
        self.assertIn("gold", tiers)

    @patch("apps.subscriptions.views.initiate_payment")
    def test_start_payment_success(self, mock_initiate):
        mock_initiate.return_value = (
            "auth123",
            "https://sandbox.zarinpal.com/pg/StartPay/auth123",
        )
        response = self.client.post(reverse("payment-start"), {"plan_id": self.plan.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["payment_url"], "https://sandbox.zarinpal.com/pg/StartPay/auth123"
        )
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(Transaction.objects.first().authority, "auth123")

    @patch("apps.subscriptions.views.initiate_payment")
    def test_start_payment_gateway_error(self, mock_initiate):
        mock_initiate.return_value = (None, None)
        response = self.client.post(reverse("payment-start"), {"plan_id": self.plan.id})
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(Transaction.objects.count(), 0)
        # D-3: the gateway failure goes through the normal exception
        # handler now, not an ad-hoc {"error": ...} body.
        self.assertEqual(response.data["code"], "payment_gateway_error")
        self.assertIn("detail", response.data)

    @patch("apps.subscriptions.views.initiate_payment")
    def test_start_payment_charges_monthly_price_times_period(self, mock_initiate):
        mock_initiate.return_value = ("auth123", "https://sandbox.zarinpal.com/pg/StartPay/auth123")
        response = self.client.post(
            reverse("payment-start"), {"plan_id": self.plan.id, "period_months": 12}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.period_months, 12)
        self.assertEqual(transaction.amount, self.plan.monthly_price * 12)
        # The gateway is charged the total, not just one month.
        charged_amount = mock_initiate.call_args[0][0]
        self.assertEqual(charged_amount, self.plan.monthly_price * 12)

    def test_start_payment_rejects_an_invalid_period(self):
        response = self.client.post(
            reverse("payment-start"), {"plan_id": self.plan.id, "period_months": 2}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.subscriptions.views.verify_payment")
    def test_callback_success_redirects_to_frontend_and_activates(self, mock_verify):
        mock_verify.return_value = (True, "ref123")
        transaction = Transaction.objects.create(
            user=self.user, plan=self.plan, amount=self.plan.monthly_price, authority="auth123"
        )

        response = self.client.get(
            reverse("payment-callback"), {"Authority": "auth123", "Status": "OK"}
        )

        # Browser is redirected back to the frontend with a success flag.
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(response.url.startswith(f"{FE}/upgrade?payment=success"))
        self.assertIn("ref_id=ref123", response.url)

        transaction.refresh_from_db()
        self.assertEqual(transaction.status, Transaction.Status.SUCCESS)
        self.assertTrue(
            Subscription.objects.filter(user=self.user, status=Subscription.Status.ACTIVE).exists()
        )
        # The computed tier now reflects the purchased plan.
        self.assertEqual(self.user.tier, "gold")

    @patch("apps.subscriptions.views.verify_payment")
    def test_callback_failed_verification_redirects_failed(self, mock_verify):
        mock_verify.return_value = (False, None)
        Transaction.objects.create(
            user=self.user, plan=self.plan, amount=self.plan.monthly_price, authority="auth9"
        )
        response = self.client.get(
            reverse("payment-callback"), {"Authority": "auth9", "Status": "OK"}
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(response.url.startswith(f"{FE}/upgrade?payment=failed"))

    @patch("apps.subscriptions.views.verify_payment")
    def test_callback_sets_period_months_and_expiry_from_the_purchase(self, mock_verify):
        mock_verify.return_value = (True, "ref123")
        Transaction.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=12,
            amount=self.plan.monthly_price * 12,
            authority="auth-12mo",
        )

        self.client.get(reverse("payment-callback"), {"Authority": "auth-12mo", "Status": "OK"})

        sub = Subscription.objects.get(user=self.user, status=Subscription.Status.ACTIVE)
        self.assertEqual(sub.period_months, 12)
        # ~1 year out, allowing for month-length variance.
        self.assertGreater(sub.expires_at, timezone.now() + timedelta(days=350))
        self.assertLess(sub.expires_at, timezone.now() + timedelta(days=380))

    @patch("apps.subscriptions.views.verify_payment")
    def test_renewing_while_active_extends_from_current_expiry_not_now(self, mock_verify):
        mock_verify.return_value = (True, "ref456")
        future_expiry = timezone.now() + timedelta(days=20)
        existing = SubscriptionFactory(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            expires_at=future_expiry,
        )
        Transaction.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=1,
            amount=self.plan.monthly_price,
            authority="auth-renew",
        )

        self.client.get(reverse("payment-callback"), {"Authority": "auth-renew", "Status": "OK"})

        existing.refresh_from_db()
        self.assertEqual(existing.status, Subscription.Status.EXPIRED)

        new_sub = Subscription.objects.get(user=self.user, status=Subscription.Status.ACTIVE)
        self.assertNotEqual(new_sub.id, existing.id)
        # Extended from the old expiry (~20 + 30 days out), not from now.
        self.assertGreater(new_sub.expires_at, future_expiry + timedelta(days=25))

    @patch("apps.subscriptions.views.verify_payment")
    def test_renewal_does_not_crash_with_prior_expired_rows(self, mock_verify):
        # D-4: update_or_create(user=...) with no status filter raised
        # MultipleObjectsReturned once a user had more than one historical
        # (non-active) Subscription row.
        mock_verify.return_value = (True, "ref789")
        SubscriptionFactory(user=self.user, plan=self.plan, status=Subscription.Status.EXPIRED)
        SubscriptionFactory(user=self.user, plan=self.plan, status=Subscription.Status.EXPIRED)
        Transaction.objects.create(
            user=self.user,
            plan=self.plan,
            period_months=1,
            amount=self.plan.monthly_price,
            authority="auth-multi",
        )

        response = self.client.get(
            reverse("payment-callback"), {"Authority": "auth-multi", "Status": "OK"}
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(response.url.startswith(f"{FE}/upgrade?payment=success"))
        self.assertEqual(
            Subscription.objects.filter(user=self.user, status=Subscription.Status.ACTIVE).count(),
            1,
        )

    def test_callback_cancelled_redirects_cancelled(self):
        response = self.client.get(reverse("payment-callback"), {"Authority": "", "Status": "NOK"})
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("payment=cancelled", response.url)


@override_settings(FRONTEND_URL=FE)
class PlanPricingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.plan = SubscriptionPlan.objects.create(tier=Tier.SILVER, monthly_price=Decimal("4.99"))
        self.admin = User.objects.create_user(
            email="admin@example.com", username="admin1", password="password", role="admin"
        )
        self.listener = User.objects.create_user(
            email="l@example.com", username="l1", password="password"
        )

    def test_admin_can_update_plan_price(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.patch(
            reverse("plan-update", args=[self.plan.id]), {"monthly_price": "6.50"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.monthly_price, Decimal("6.50"))

    def test_price_update_cannot_change_tier(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.patch(
            reverse("plan-update", args=[self.plan.id]),
            {"monthly_price": "7.00", "tier": "gold"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.tier, Tier.SILVER)  # tier is read-only

    def test_non_admin_cannot_update_price(self):
        self.client.force_authenticate(user=self.listener)
        res = self.client.patch(
            reverse("plan-update", args=[self.plan.id]), {"monthly_price": "1.00"}
        )
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))
