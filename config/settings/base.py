from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    'daphne',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "django_filters",
    "corsheaders",
    "apps.common",
    "apps.accounts",
    "apps.catalog",
    "apps.playlists",
    "apps.subscriptions",
    'channels',
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.MediaCorsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres:///spotify_be"),
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

MEDIA_IMAGE_MAX_BYTES = env.int("MEDIA_IMAGE_MAX_BYTES", default=5 * 1024 * 1024)
MEDIA_AUDIO_MAX_BYTES = env.int("MEDIA_AUDIO_MAX_BYTES", default=50 * 1024 * 1024)
MEDIA_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
MEDIA_AUDIO_EXTENSIONS = [".mp3", ".wav", ".flac"]
FILE_UPLOAD_PERMISSIONS = 0o644

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("djangorestframework_camel_case.render.CamelCaseJSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Spotify Clone API",
    "VERSION": "1.0.0",
    "DESCRIPTION": """
Spotify-clone REST API — a music streaming platform with four roles (**listener**, **artist**,
**support**, **admin**) and three listener subscription tiers (**basic**, **silver**, **gold**).

### Roles & tiers

| Feature | Basic (Free) | Silver | Gold |
|---|---|---|---|
| Daily stream limit | 60 | unlimited | unlimited |
| Playlist limit | 6 | 100 | unlimited |
| Profile picture upload | No | Yes | Yes |
| Track download | No | Yes | Yes |
| Early access to new tracks | No | No | Yes |
| Song/listener statistics | No | No | Yes |

`role` is fixed at registration/approval and travels on the JWT. **Tier is deliberately not on the
JWT** — it is computed live from the user's active `Subscription` (`User.tier`), because tier can
change the instant a payment completes and a stale JWT claim would misrepresent access until the
token expires. Call `GET /api/auth/me/` for the current tier; don't infer it from the token.

### Authentication

1. `POST /api/auth/login/` (or `/api/auth/register/listener/`, which also logs in) returns
   `{user, access, refresh}`.
2. Send `Authorization: Bearer <access>` on every subsequent request — use "Authorize" above.
3. `access` expires in 30 minutes. `POST /api/auth/refresh/` with the current `refresh` **rotates
   and blacklists** it — store the *new* `refresh` from the response, or the next refresh call 401s.

`POST /api/auth/register/artist/` does **not** return tokens — the account is `pending` until a
support/admin user approves it.

### Conventions

- **camelCase over the wire, snake_case in Python.** Request/response bodies are camelCase
  (`djangorestframework-camel-case`); query params are camelCase only where a view explicitly
  says so (e.g. `?earlyAccess`, `?ordering=-playCount`).
- **Errors** are always `{"detail": string, "code": string, "fields": object|null}` — `fields` is
  populated only for field-level validation errors.
- **Pagination**: `?page` / `?pageSize` (max 100).
- **Media URLs** (`avatar`, album/track/playlist `cover`, `audioHigh`/`audioLow`) are
  unauthenticated capability URLs — the path contains a random, unguessable suffix rather than a
  signed/expiring token, because `<img src>`/`<audio src>` can't send an `Authorization` header.
  `GET /api/tracks/{id}/download/` is the one endpoint with a real tier check (silver/gold) on
  top of that, and both media serving and downloads support HTTP Range (`206 Partial Content`).

### Demo accounts (all `password123`)

`listener@demo.com` (basic) · `silver@demo.com` · `gold@demo.com` · `nova@demo.com` /
`echo@demo.com` (approved artists) · `pending-artist@demo.com` (awaiting approval) ·
`support@demo.com` · `admin@demo.com`.

### Realtime (WebSocket) — group listening

`ws://<host>/ws/session/{sessionId}/` (`GroupSessionConsumer`) is **outside this OpenAPI schema** —
OpenAPI 3.0 has no way to describe WebSockets. The socket is session/cookie-authenticated (Django's
`AuthMiddlewareStack`), **not** the JWT bearer token the REST API above uses, since a browser's
WebSocket handshake carries cookies, not custom headers. Once connected, every client in the group
sends and receives the same frame shape:

```json
{"action": "play" | "pause" | "seek", "progress": <seconds>}
```

The server rebroadcasts each frame to the rest of the group unchanged — there is no server-side
validation of `action`'s value or `progress`'s type/range today.
""",
    "CONTACT": {"name": "Spotify Clone API"},
    "LICENSE": {"name": "MIT"},
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api",
    "SORT_OPERATION_PARAMETERS": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "AccountStatus": "apps.accounts.models.AccountStatus",
        "SubscriptionStatus": "apps.subscriptions.models.Subscription.Status",
        "TransactionStatus": "apps.subscriptions.models.Transaction.Status",
        "PayoutStatus": "apps.reports.models.ArtistPayout.Status",
    },
    "TAGS": [
        {"name": "Auth", "description": "Registration, login, token refresh, password reset."},
        {"name": "Account", "description": "The current user's profile, avatar, and preferences."},
        {"name": "Users & Follows", "description": "Public user profiles and the follow graph."},
        {"name": "Artists", "description": "Artist profiles, approval, and sample works."},
        {"name": "Albums", "description": "Album CRUD and cover art."},
        {"name": "Tracks", "description": "Track CRUD, search/filter/sort, cover/audio uploads."},
        {"name": "Streaming", "description": "Playback recording and authenticated downloads."},
        {"name": "Recommendations", "description": "Personalized track recommendations."},
        {"name": "Playlists", "description": "Playlist CRUD, track ordering, and covers."},
        {"name": "Reports", "description": "Artist, support, and admin reporting/statistics."},
        {
            "name": "Payments & Subscriptions",
            "description": "Subscription plans and payment gateway integration.",
        },
    ],
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "deepLinking": True,
        "filter": True,
        "docExpansion": "none",
        "tryItOutEnabled": True,
    },
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "drf_spectacular.contrib.djangorestframework_camel_case.camelize_serializer_fields",
        "apps.common.openapi.add_common_error_responses",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])

# Development uses an in-memory channel layer for event handling.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}
