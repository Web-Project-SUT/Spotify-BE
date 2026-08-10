from django.urls import path

from .views import PaymentCallbackView, PaymentStartView, PlanListView

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="plan-list"),
    path("pay/start/", PaymentStartView.as_view(), name="payment-start"),
    path("pay/callback/", PaymentCallbackView.as_view(), name="payment-callback"),
]
