from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription, SubscriptionPlan, Transaction
from .serializers import SubscriptionPlanSerializer
from .services import initiate_payment, verify_payment


class PlanListView(generics.ListAPIView):
    """Public list of active plans so the frontend can start a payment."""

    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("monthly_price")
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class PaymentStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get("plan_id")
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        callback_url = request.build_absolute_uri(reverse("payment-callback"))
        authority, payment_url = initiate_payment(
            plan.monthly_price, f"Subscription {plan.tier}", callback_url
        )

        if authority:
            Transaction.objects.create(
                user=request.user, plan=plan, amount=plan.monthly_price, authority=authority
            )
            return Response({"payment_url": payment_url}, status=status.HTTP_200_OK)
        return Response(
            {"error": "Payment gateway error"}, status=status.HTTP_502_BAD_GATEWAY
        )


class PaymentCallbackView(APIView):
    """Zarinpal redirects the user's browser here after payment.

    We verify, activate the subscription, then redirect the browser back to
    the frontend with a ?payment= result flag rather than returning JSON, so
    the user lands on a real page.
    """

    permission_classes = [AllowAny]

    def _fe(self, result: str, **params) -> str:
        base = settings.FRONTEND_URL.rstrip("/")
        query = "&".join([f"payment={result}", *[f"{k}={v}" for k, v in params.items()]])
        return f"{base}/upgrade?{query}"

    def get(self, request):
        authority = request.GET.get("Authority")
        payment_status = request.GET.get("Status")

        if not authority or payment_status != "OK":
            return redirect(self._fe("cancelled"))

        transaction = get_object_or_404(
            Transaction, authority=authority, status=Transaction.Status.PENDING
        )
        is_verified, ref_id = verify_payment(authority, transaction.amount)

        if is_verified:
            transaction.status = Transaction.Status.SUCCESS
            transaction.ref_id = ref_id
            transaction.save()

            Subscription.objects.update_or_create(
                user=transaction.user,
                defaults={
                    "plan": transaction.plan,
                    "period_months": 1,
                    "price_paid": transaction.amount,
                    "starts_at": timezone.now(),
                    "expires_at": timezone.now() + timedelta(days=30),
                    "status": Subscription.Status.ACTIVE,
                },
            )
            return redirect(self._fe("success", ref_id=ref_id))

        transaction.status = Transaction.Status.FAILED
        transaction.save()
        return redirect(self._fe("failed"))
