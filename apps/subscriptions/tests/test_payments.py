from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model

from apps.subscriptions.models import SubscriptionPlan, Transaction, Subscription, Tier

User = get_user_model()

class PaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # The email argument is required by your custom user model
        self.user = User.objects.create_user(
            email="test@example.com", 
            username="testuser", 
            password="password"
        )
        self.client.force_authenticate(user=self.user)
        self.plan = SubscriptionPlan.objects.create(tier=Tier.GOLD, monthly_price=Decimal("9.99"))

    @patch('apps.subscriptions.views.initiate_payment')
    def test_start_payment_success(self, mock_initiate):
        mock_initiate.return_value = ("auth123", "https://sandbox.zarinpal.com/pg/StartPay/auth123")
        
        url = reverse('payment-start')
        response = self.client.post(url, {"plan_id": self.plan.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_url"], "https://sandbox.zarinpal.com/pg/StartPay/auth123")
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(Transaction.objects.first().authority, "auth123")

    @patch('apps.subscriptions.views.verify_payment')
    def test_callback_payment_success(self, mock_verify):
        mock_verify.return_value = (True, "ref123")
        
        transaction = Transaction.objects.create(
            user=self.user, plan=self.plan, amount=self.plan.monthly_price, authority="auth123"
        )
        
        url = reverse('payment-callback')
        response = self.client.get(url, {"Authority": "auth123", "Status": "OK"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, Transaction.Status.SUCCESS)
        self.assertTrue(Subscription.objects.filter(user=self.user, status=Subscription.Status.ACTIVE).exists())