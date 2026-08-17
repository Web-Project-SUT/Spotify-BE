from django.urls import path

from . import views

urlpatterns = [
    path(
        "auth/register/listener/",
        views.RegisterListenerView.as_view(),
        name="register-listener",
    ),
    path(
        "auth/register/artist/",
        views.RegisterArtistView.as_view(),
        name="register-artist",
    ),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/refresh/", views.RefreshView.as_view(), name="refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/me/avatar/", views.AvatarView.as_view(), name="me-avatar"),
    path("auth/me/preferences/", views.PreferencesView.as_view(), name="me-preferences"),
    path(
        "auth/me/notifications/",
        views.NotificationListView.as_view(),
        name="me-notifications",
    ),
    path(
        "auth/me/notifications/read/",
        views.NotificationMarkReadView.as_view(),
        name="me-notifications-read",
    ),
    path(
        "auth/me/notifications/<uuid:pk>/read/",
        views.NotificationItemReadView.as_view(),
        name="me-notification-item-read",
    ),
    path(
        "auth/me/notifications/<uuid:pk>/",
        views.NotificationItemView.as_view(),
        name="me-notification-item",
    ),
    path(
        "auth/password-reset/",
        views.PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "auth/password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("artists/", views.ArtistListView.as_view(), name="artist-list"),
    path("artists/me/", views.ArtistMeView.as_view(), name="artist-me"),
    path("artists/pending/", views.PendingArtistListView.as_view(), name="artist-pending"),
    path(
        "artists/me/sample-works/",
        views.SampleWorkListCreateView.as_view(),
        name="sample-work-list-create",
    ),
    path(
        "artists/me/sample-works/<uuid:pk>/",
        views.SampleWorkDeleteView.as_view(),
        name="sample-work-delete",
    ),
    path("artists/<uuid:pk>/", views.ArtistDetailView.as_view(), name="artist-detail"),
    path("artists/<uuid:pk>/approve/", views.ArtistApproveView.as_view(), name="artist-approve"),
    path("artists/<uuid:pk>/reject/", views.ArtistRejectView.as_view(), name="artist-reject"),
    path(
        "artists/<uuid:pk>/sample-works/",
        views.ArtistSampleWorkListView.as_view(),
        name="artist-sample-works",
    ),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:pk>/follow/", views.FollowView.as_view(), name="user-follow"),
]
