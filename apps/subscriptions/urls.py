from django.urls import path

from .views import (
    PaymentCallbackView,
    PaymentStartView,
    PlanListView,
    PlanPriceUpdateView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="plan-list"),
    path("plans/<int:pk>/", PlanPriceUpdateView.as_view(), name="plan-update"),
    path("pay/start/", PaymentStartView.as_view(), name="payment-start"),
    path("pay/callback/", PaymentCallbackView.as_view(), name="payment-callback"),
]
