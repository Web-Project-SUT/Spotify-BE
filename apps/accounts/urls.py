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
    path("artists/<uuid:pk>/", views.ArtistDetailView.as_view(), name="artist-detail"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:pk>/follow/", views.FollowView.as_view(), name="user-follow"),
]
