from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers, status
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer

from apps.common.openapi import Params, Tags

from .models import SubscriptionPlan, Transaction, Subscription
from .services import initiate_payment, verify_payment

class PaymentStartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[Tags.PAYMENTS],
        summary="Start a subscription payment",
        description=(
            "Creates a pending `Transaction` and returns a Zarinpal `payment_url` to redirect "
            "the user to. Note the request field is `planId` — `CamelCaseJSONParser` un-"
            "camelizes the body before the view reads `request.data.get(\"plan_id\")`."
        ),
        request=inline_serializer(
            "PaymentStartRequest", fields={"plan_id": serializers.UUIDField()}
        ),
        responses={
            200: inline_serializer(
                "PaymentStartResponse", fields={"payment_url": serializers.URLField()}
            ),
            500: OpenApiResponse(
                response=inline_serializer(
                    "PaymentGatewayError", fields={"error": serializers.CharField()}
                ),
                description="The payment gateway could not be reached or rejected the request.",
            ),
        },
    )
    def post(self, request):
        plan_id = request.data.get("plan_id")
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        callback_url = request.build_absolute_uri(reverse('payment-callback'))
        authority, payment_url = initiate_payment(plan.monthly_price, f"Subscription {plan.tier}", callback_url)
        
        if authority:
            Transaction.objects.create(
                user=request.user,
                plan=plan,
                amount=plan.monthly_price,
                authority=authority
            )
            return Response({"payment_url": payment_url}, status=status.HTTP_200_OK)
        return Response({"error": "Payment gateway error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PaymentCallbackView(APIView):
    @extend_schema(
        tags=[Tags.PAYMENTS],
        summary="Zarinpal payment callback",
        description=(
            "The gateway redirects the user's browser here with no `Authorization` header, yet "
            "this view has no `permission_classes` of its own and so inherits the global "
            "`IsAuthenticated` default — as written, this callback cannot succeed for a real "
            "gateway redirect (see PR write-up). Transaction lifecycle: `pending` -> `success` "
            "on a verified callback, `pending` -> `failed` otherwise."
        ),
        parameters=[Params.ZARINPAL_AUTHORITY, Params.ZARINPAL_STATUS],
        request=None,
        responses={
            200: inline_serializer(
                "PaymentCallbackResponse",
                fields={"message": serializers.CharField(), "ref_id": serializers.CharField()},
            ),
            400: OpenApiResponse(
                response=inline_serializer(
                    "PaymentCallbackError", fields={"error": serializers.CharField()}
                ),
                description="Payment was cancelled, failed, or verification failed.",
            ),
        },
    )
    def get(self, request):
        authority = request.GET.get("Authority")
        payment_status = request.GET.get("Status")
        
        if not authority or payment_status != "OK":
            return Response({"error": "Payment failed or cancelled"}, status=status.HTTP_400_BAD_REQUEST)
            
        transaction = get_object_or_404(Transaction, authority=authority, status=Transaction.Status.PENDING)
        is_verified, ref_id = verify_payment(authority, transaction.amount)
        
        if is_verified:
            transaction.status = Transaction.Status.SUCCESS
            transaction.ref_id = ref_id
            transaction.save()
            
            # فعال‌سازی یا تمدید اشتراک کاربر پس از موفقیت پرداخت
            Subscription.objects.update_or_create(
                user=transaction.user,
                defaults={
                    "plan": transaction.plan,
                    "period_months": 1,
                    "price_paid": transaction.amount,
                    "starts_at": timezone.now(),
                    "expires_at": timezone.now() + timedelta(days=30),
                    "status": Subscription.Status.ACTIVE
                }
            )
            return Response({"message": "Payment successful", "ref_id": ref_id}, status=status.HTTP_200_OK)
        
        transaction.status = Transaction.Status.FAILED
        transaction.save()
        return Response({"error": "Payment verification failed"}, status=status.HTTP_400_BAD_REQUEST)