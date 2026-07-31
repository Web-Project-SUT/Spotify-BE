"""Shared drf-spectacular building blocks.

Every per-app `extend_schema`/`extend_schema_view` annotation imports from
here rather than re-declaring error envelopes, tags, or media-endpoint
decorators inline — this is the one place that changes if the error shape,
tag list, or media-endpoint pattern ever changes.
"""

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated


class ErrorSerializer(serializers.Serializer):
    """The exact envelope `apps.common.exceptions.api_exception_handler` returns."""

    detail = serializers.CharField()
    code = serializers.CharField()
    fields = serializers.DictField(required=False, allow_null=True)


class Tags:
    AUTH = "Auth"
    ACCOUNT = "Account"
    USERS_FOLLOWS = "Users & Follows"
    ARTISTS = "Artists"
    ALBUMS = "Albums"
    TRACKS = "Tracks"
    STREAMING = "Streaming"
    RECOMMENDATIONS = "Recommendations"
    PLAYLISTS = "Playlists"
    REPORTS = "Reports"
    PAYMENTS = "Payments & Subscriptions"


def _error_example(name, detail, code, fields=None):
    return OpenApiExample(name, value={"detail": detail, "code": code, "fields": fields})


class Responses:
    """`OpenApiResponse` singletons for the error statuses every operation can hit."""

    VALIDATION_400 = OpenApiResponse(
        response=ErrorSerializer,
        description="Validation failed.",
        examples=[
            _error_example(
                "validation_error",
                "Validation failed.",
                "error",
                fields={"field_name": ["This field is required."]},
            )
        ],
    )
    UNAUTHORIZED_401 = OpenApiResponse(
        response=ErrorSerializer,
        description="Missing, invalid, or expired bearer token.",
        examples=[
            _error_example(
                "not_authenticated",
                "Authentication credentials were not provided.",
                "not_authenticated",
            )
        ],
    )
    FORBIDDEN_403 = OpenApiResponse(
        response=ErrorSerializer,
        description="Authenticated, but not permitted to perform this action.",
        examples=[
            _error_example(
                "permission_denied",
                "You do not have permission to perform this action.",
                "permission_denied",
            )
        ],
    )
    NOT_FOUND_404 = OpenApiResponse(
        response=ErrorSerializer,
        description="No resource exists at this path.",
        examples=[_error_example("not_found", "Not found.", "not_found")],
    )
    QUOTA_403 = OpenApiResponse(
        response=ErrorSerializer,
        description="The user's subscription tier has hit a quota limit.",
        examples=[
            _error_example(
                "quota_exceeded",
                "Limit of 6 reached for your subscription tier.",
                "quota_exceeded",
            ),
            _error_example(
                "file_too_large",
                "File exceeds the maximum allowed size.",
                "file_too_large",
            ),
            _error_example(
                "unsupported_file_type",
                "Unsupported file type.",
                "unsupported_file_type",
            ),
        ],
    )


class Params:
    """Query parameters that are otherwise invisible in the generated schema."""

    PERIOD = OpenApiParameter(
        name="period",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Month to report on, `YYYY-MM`. Defaults to the current period when omitted.",
    )
    MONTHS = OpenApiParameter(
        name="months",
        type=int,
        location=OpenApiParameter.QUERY,
        description=(
            "Number of trailing months in the revenue series. Silently clamped to "
            "[1, 24]; defaults to 6."
        ),
    )
    PAGE = OpenApiParameter(
        name="page",
        type=int,
        location=OpenApiParameter.QUERY,
        description="1-indexed page number.",
    )
    PAGE_SIZE = OpenApiParameter(
        name="pageSize",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Items per page, max 100.",
    )
    ZARINPAL_AUTHORITY = OpenApiParameter(
        name="Authority",
        type=str,
        location=OpenApiParameter.QUERY,
        required=True,
        description="Zarinpal payment authority token for this transaction.",
    )
    ZARINPAL_STATUS = OpenApiParameter(
        name="Status",
        type=str,
        location=OpenApiParameter.QUERY,
        required=True,
        description='Zarinpal gateway result, literally `"OK"` or `"NOK"`.',
    )

    @staticmethod
    def ORDERING(*values):
        return OpenApiParameter(
            name="ordering",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Sort key: one of " + ", ".join(f"`{v}`" for v in values) + ". "
            "Prefix with `-` to reverse.",
        )


def media_resource_schema(read_serializer, upload_serializer, *, summary_noun, tags, quota=False):
    """`extend_schema_view` decorator for a `MediaResourceView` subclass's PUT/DELETE.

    Replaces the near-identical hand-written decorator that used to sit on every
    media endpoint (avatar, album/track/playlist cover, track audio).
    """
    put_responses = {200: read_serializer, 400: Responses.VALIDATION_400}
    if quota:
        put_responses[403] = Responses.QUOTA_403
    return extend_schema_view(
        put=extend_schema(
            summary=f"Replace the {summary_noun}",
            request={"multipart/form-data": upload_serializer},
            responses=put_responses,
            tags=tags,
        ),
        delete=extend_schema(
            summary=f"Remove the {summary_noun}",
            responses={204: None},
            tags=tags,
        ),
    )


def _find_error_component(result):
    schemas = result.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        if {"detail", "code", "fields"} <= schema.get("properties", {}).keys():
            return name
    return None


def _error_response(description, component_name):
    return {
        "description": description,
        "content": {
            "application/json": {"schema": {"$ref": f"#/components/schemas/{component_name}"}}
        },
    }


def _is_bare_authenticated(permissions):
    return len(permissions) <= 1 and all(isinstance(p, IsAuthenticated) for p in permissions)


def add_common_error_responses(result, generator, request, public):
    """Postprocessing hook: stamp shared 4xx responses onto every operation.

    Runs after schema generation, walking the finished schema plus a fresh
    view instance per operation (via `generator._get_paths_and_endpoints()`,
    the same private helper drf-spectacular's own `parse()` uses) — never a
    view file. `401` is added wherever the operation already requires auth;
    `403` wherever the resolved view carries any permission beyond bare
    `IsAuthenticated` (a role/tier/ownership check) or a `quota_class`; `404`
    wherever the path has a `{param}`; `400` wherever a request body exists.
    Never overwrites a status code a view's own `extend_schema` already
    declared (e.g. `self_follow`'s inline 400 examples).
    """
    error_component = _find_error_component(result)
    if error_component is None:
        return result

    gated_operations = set()
    for path, _path_regex, method, view in generator._get_paths_and_endpoints():
        try:
            view_permissions = view.get_permissions()
        except Exception:
            view_permissions = []
        gated = not _is_bare_authenticated(view_permissions) or bool(
            getattr(view, "quota_class", None)
        )
        if gated:
            gated_operations.add((path, method.lower()))

    for path, path_item in result.get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            responses = operation.setdefault("responses", {})
            if operation.get("security"):
                responses.setdefault(
                    "401",
                    _error_response(
                        "Missing, invalid, or expired bearer token.", error_component
                    ),
                )
                if (path, method) in gated_operations:
                    responses.setdefault(
                        "403",
                        _error_response(
                            "Authenticated, but not permitted to perform this action.",
                            error_component,
                        ),
                    )
            if any(p.get("in") == "path" for p in operation.get("parameters", [])):
                responses.setdefault(
                    "404", _error_response("No resource exists at this path.", error_component)
                )
            if operation.get("requestBody"):
                responses.setdefault(
                    "400", _error_response("Validation failed.", error_component)
                )
    return result
