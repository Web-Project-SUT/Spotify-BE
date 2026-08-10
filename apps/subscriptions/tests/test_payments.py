from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.subscriptions.models import SubscriptionPlan, Subscription, Tier, Transaction

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
            Subscription.objects.filter(
                user=self.user, status=Subscription.Status.ACTIVE
            ).exists()
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

    def test_callback_cancelled_redirects_cancelled(self):
        response = self.client.get(
            reverse("payment-callback"), {"Authority": "", "Status": "NOK"}
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("payment=cancelled", response.url)
