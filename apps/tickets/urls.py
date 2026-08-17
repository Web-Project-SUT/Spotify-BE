from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("tickets", views.TicketViewSet, basename="ticket")

urlpatterns = [
    path(
        "tickets/<uuid:ticket_id>/messages/",
        views.TicketMessagesView.as_view(),
        name="ticket-messages",
    ),
] + router.urls
