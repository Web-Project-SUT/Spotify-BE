from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin

from .models import SubscriptionPlan, Transaction
from .serializers import (
    PaymentStartSerializer,
    PlanPriceUpdateSerializer,
    SubscriptionPlanSerializer,
)
from .services import PaymentGatewayError, activate_subscription, initiate_payment, verify_payment


class PlanListView(generics.ListAPIView):
    """Public list of active plans so the frontend can start a payment."""

    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by("monthly_price")
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class PlanPriceUpdateView(generics.UpdateAPIView):
    """Admin-only price editing (Task 29 — dynamic subscription pricing)."""

    queryset = SubscriptionPlan.objects.all()
    serializer_class = PlanPriceUpdateSerializer
    permission_classes = [IsAdmin]


class PaymentStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan"]
        period_months = int(serializer.validated_data["period_months"])
        amount = plan.monthly_price * period_months

        callback_url = request.build_absolute_uri(reverse("payment-callback"))
        authority, payment_url = initiate_payment(
            amount, f"Subscription {plan.tier} x{period_months}mo", callback_url
        )

        if not authority:
            raise PaymentGatewayError()

        Transaction.objects.create(
            user=request.user,
            plan=plan,
            period_months=period_months,
            amount=amount,
            authority=authority,
        )
        return Response({"payment_url": payment_url}, status=status.HTTP_200_OK)


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

            activate_subscription(transaction)
            return redirect(self._fe("success", ref_id=ref_id))

        transaction.status = Transaction.Status.FAILED
        transaction.save()
        return redirect(self._fe("failed"))
