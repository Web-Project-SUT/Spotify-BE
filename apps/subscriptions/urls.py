from django.urls import path
from .views import PaymentStartView, PaymentCallbackView

urlpatterns = [
    path('pay/start/', PaymentStartView.as_view(), name='payment-start'),
    path('pay/callback/', PaymentCallbackView.as_view(), name='payment-callback'),
]