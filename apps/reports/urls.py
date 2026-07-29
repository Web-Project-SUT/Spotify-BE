from django.urls import path

from . import views

urlpatterns = [
    path("reports/me/listening/", views.ListeningStatsView.as_view(), name="listening-stats"),
    path(
        "reports/artists/me/summary/",
        views.ArtistMeSummaryView.as_view(),
        name="artist-me-summary",
    ),
    path(
        "reports/artists/me/tracks/",
        views.ArtistMeTracksView.as_view(),
        name="artist-me-tracks",
    ),
    path(
        "reports/artists/me/payouts/",
        views.ArtistMePayoutsView.as_view(),
        name="artist-me-payouts",
    ),
    path(
        "reports/artists/<uuid:pk>/summary/",
        views.ArtistSummaryView.as_view(),
        name="artist-summary",
    ),
    path("reports/payouts/", views.ArtistPayoutListView.as_view(), name="payout-list"),
    path(
        "reports/payouts/generate/",
        views.GeneratePayoutsView.as_view(),
        name="payout-generate",
    ),
    path(
        "reports/payouts/<uuid:pk>/settle/",
        views.SettlePayoutView.as_view(),
        name="payout-settle",
    ),
    path("reports/admin/overview/", views.AdminOverviewView.as_view(), name="admin-overview"),
]
