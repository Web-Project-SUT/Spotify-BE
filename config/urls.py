import re

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.common.views import serve_media

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.catalog.urls")),
    path("api/", include("apps.playlists.urls")),
    path("api/", include("apps.reports.urls")),
    path("api/", include("apps.tickets.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/subscriptions/", include("apps.subscriptions.urls")),
]

if settings.DEBUG:
    # Media: serve_media (not django.conf.urls.static.static) because the
    # frontend's <audio> needs Range responses for seeking.
    urlpatterns += [
        re_path(r"^%s(?P<path>.*)$" % re.escape(settings.MEDIA_URL.lstrip("/")), serve_media),
    ]
    # Static: resolved through the staticfiles finders, so the admin CSS is
    # served under daphne/ASGI too. Serving STATIC_ROOT instead would 404
    # until collectstatic has run, which nothing does.
    urlpatterns += staticfiles_urlpatterns()
