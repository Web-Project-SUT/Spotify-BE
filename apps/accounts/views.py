from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.openapi import ErrorSerializer, Responses, Tags, media_resource_schema
from apps.common.permissions import IsApprovedArtist, IsArtist, IsListenerOrArtist, IsSupportOrAdmin
from apps.common.quotas import AvatarUploadQuota
from apps.common.views import MediaResourceView

from . import services
from .models import AccountStatus, ArtistProfile, Follow, SampleWork, User
from .serializers import (
    ArtistDetailSerializer,
    ArtistListSerializer,
    ArtistMeSerializer,
    AvatarUploadSerializer,
    CustomTokenObtainPairSerializer,
    MeUpdateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterArtistSerializer,
    RegisterListenerSerializer,
    SampleWorkSerializer,
    SampleWorkUploadSerializer,
    UserMeSerializer,
    UserPreferencesSerializer,
    UserPublicSerializer,
)


@extend_schema(
    tags=[Tags.AUTH],
    auth=[],
    summary="Register a listener",
    description="Creates a `listener` account and logs it in immediately.",
    responses={
        201: inline_serializer(
            "RegisterListenerResponse",
            fields={
                "user": UserMeSerializer(),
                "access": serializers.CharField(),
                "refresh": serializers.CharField(),
            },
        ),
        400: Responses.VALIDATION_400,
    },
)
class RegisterListenerView(generics.CreateAPIView):
    serializer_class = RegisterListenerSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        data = {
            "user": UserMeSerializer(user, context=self.get_serializer_context()).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=[Tags.AUTH],
    auth=[],
    summary="Register an artist",
    description=(
        "Creates an `artist` account **pending** support/admin approval. Unlike listener "
        "registration, no tokens are returned — the account cannot log in until approved."
    ),
    responses={
        201: inline_serializer("RegisterArtistResponse", fields={"user": UserMeSerializer()}),
        400: Responses.VALIDATION_400,
    },
)
class RegisterArtistView(generics.CreateAPIView):
    serializer_class = RegisterArtistSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {"user": UserMeSerializer(user, context=self.get_serializer_context()).data}
        return Response(data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    post=extend_schema(
        tags=[Tags.AUTH],
        auth=[],
        summary="Log in",
        responses={400: Responses.VALIDATION_400},
    )
)
class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema_view(
    post=extend_schema(
        tags=[Tags.AUTH],
        auth=[],
        summary="Refresh the access token",
        description=(
            "Exchanges a `refresh` token for a new `access` token. `ROTATE_REFRESH_TOKENS` and "
            "`BLACKLIST_AFTER_ROTATION` are both on: the response also carries a **new** "
            "`refresh` token and the one just used is blacklisted. Callers must persist the "
            "rotated `refresh` — retrying with the old one 401s."
        ),
        responses={400: Responses.VALIDATION_400},
    )
)
class RefreshView(TokenRefreshView):
    pass


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=[Tags.AUTH],
        summary="Log out",
        description="Blacklists the given `refresh` token so it can't obtain new access tokens.",
        request={
            "application/json": {"type": "object", "properties": {"refresh": {"type": "string"}}}
        },
        responses={204: None, 400: Responses.VALIDATION_400},
    )
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "refresh is required.", "code": "refresh_required", "fields": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid token.", "code": "token_not_valid", "fields": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(tags=[Tags.ACCOUNT], summary="Get the current user"),
    put=extend_schema(
        tags=[Tags.ACCOUNT],
        summary="Update the current user",
        description=(
            "**Known quirk:** `update()` forces `partial=True` internally, so this behaves "
            "identically to PATCH — omitted fields are left unchanged rather than rejected as "
            "missing."
        ),
        request=MeUpdateSerializer,
        responses={200: UserMeSerializer, 400: Responses.VALIDATION_400},
    ),
    patch=extend_schema(
        tags=[Tags.ACCOUNT],
        summary="Partially update the current user",
        request=MeUpdateSerializer,
        responses={200: UserMeSerializer, 400: Responses.VALIDATION_400},
    ),
    delete=extend_schema(
        tags=[Tags.ACCOUNT], summary="Delete the current user's account", responses={204: None}
    ),
)
class MeView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserMeSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return MeUpdateSerializer
        return UserMeSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(UserMeSerializer(instance, context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=[Tags.ACCOUNT],
        summary="Get the current user's preferences",
        description=(
            "Preferences sync across every device the user logs into. camelCase fields: "
            "`language` (`en`/`fa`/`es`), `notifLimit`, `volume` (0-100), `repeatMode` "
            "(`off`/`all`/`one`), `shuffle`, `playbackQuality` (`high`/`low`)."
        ),
    ),
    patch=extend_schema(
        tags=[Tags.ACCOUNT],
        summary="Update the current user's preferences",
        description=(
            "PATCH-only by design — PUT would require every field in one request, so a device "
            "sending its stale full view could silently revert fields another device changed "
            "since."
        ),
        responses={200: UserPreferencesSerializer, 400: Responses.VALIDATION_400},
    ),
)
class PreferencesView(generics.RetrieveUpdateAPIView):
    # No role gate: every authenticated user (listener, artist, support,
    # admin) has preferences. PUT is deliberately excluded (via
    # http_method_names) — DRF's PUT requires every writable field, so a
    # device sending its stale full view would silently revert fields another
    # device changed since. PATCH gives free per-field merge instead.
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPreferencesSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return services.get_preferences(self.request.user)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=[Tags.AUTH],
        auth=[],
        summary="Request a password reset email",
        description=(
            "Always returns 204 whether or not the email matches an account, to avoid leaking "
            "which emails are registered."
        ),
        request=PasswordResetRequestSerializer,
        responses={204: None, 400: Responses.VALIDATION_400},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user:
            uid = urlsafe_base64_encode(str(user.pk).encode())
            token = default_token_generator.make_token(user)
            send_mail(
                subject="Reset your password",
                message=f"Use this link to reset your password: /reset-password/{uid}/{token}/",
                from_email=None,
                recipient_list=[user.email],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=[Tags.AUTH],
        auth=[],
        summary="Confirm a password reset",
        request=PasswordResetConfirmSerializer,
        responses={204: None, 400: Responses.VALIDATION_400},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            uid = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response(
                {"detail": "Invalid reset link.", "code": "invalid_reset_link", "fields": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not default_token_generator.check_token(user, data["token"]):
            return Response(
                {"detail": "Invalid or expired token.", "code": "invalid_token", "fields": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        tags=[Tags.ARTISTS],
        summary="List approved artists",
        description="Only artists whose account `status` is `active` (approved) appear here.",
    )
)
class ArtistListView(generics.ListAPIView):
    serializer_class = ArtistListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ArtistProfile.objects.filter(user__status=AccountStatus.ACTIVE).select_related(
            "user"
        )


@extend_schema_view(
    get=extend_schema(
        tags=[Tags.ARTISTS],
        summary="Get an artist's public profile",
        responses={404: Responses.NOT_FOUND_404},
    )
)
class ArtistDetailView(generics.RetrieveAPIView):
    serializer_class = ArtistDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "pk"
    lookup_field = "user_id"

    def get_queryset(self):
        return ArtistProfile.objects.select_related("user")


@extend_schema_view(
    put=extend_schema(
        tags=[Tags.ARTISTS],
        summary="Update the current artist's profile",
        responses={200: ArtistMeSerializer, 400: Responses.VALIDATION_400},
    ),
    patch=extend_schema(
        tags=[Tags.ARTISTS],
        summary="Partially update the current artist's profile",
        responses={200: ArtistMeSerializer, 400: Responses.VALIDATION_400},
    ),
)
class ArtistMeView(generics.UpdateAPIView):
    serializer_class = ArtistMeSerializer
    permission_classes = [permissions.IsAuthenticated, IsApprovedArtist]

    def get_object(self):
        return self.request.user.artist_profile


@extend_schema_view(
    get=extend_schema(
        tags=[Tags.USERS_FOLLOWS],
        summary="Get a user's public profile",
        responses={404: Responses.NOT_FOUND_404},
    )
)
class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserPublicSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all()


class FollowView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsListenerOrArtist]

    @extend_schema(
        tags=[Tags.USERS_FOLLOWS],
        summary="Follow a user",
        request=None,
        responses={
            201: OpenApiResponse(description="Now following this user."),
            200: OpenApiResponse(description="Was already following this user; no-op."),
            400: OpenApiResponse(
                response=ErrorSerializer,
                description="Attempted to follow yourself.",
                examples=[
                    OpenApiExample(
                        "self_follow",
                        value={
                            "detail": "You cannot follow yourself.",
                            "code": "self_follow",
                            "fields": None,
                        },
                    )
                ],
            ),
        },
    )
    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        if target.id == request.user.id:
            return Response(
                {
                    "detail": "You cannot follow yourself.",
                    "code": "self_follow",
                    "fields": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        _, created = Follow.objects.get_or_create(follower=request.user, following=target)
        return Response(status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(tags=[Tags.USERS_FOLLOWS], summary="Unfollow a user", responses={204: None})
    def delete(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        Follow.objects.filter(follower=request.user, following=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@media_resource_schema(
    UserMeSerializer, AvatarUploadSerializer, summary_noun="avatar", tags=[Tags.ACCOUNT], quota=True
)
class AvatarView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated]
    media_fields = ("avatar",)
    upload_serializer_class = AvatarUploadSerializer
    read_serializer_class = UserMeSerializer
    quota_class = AvatarUploadQuota

    def get_object(self):
        return self.request.user


@extend_schema_view(
    get=extend_schema(tags=[Tags.ARTISTS], summary="List the current artist's sample works")
)
class SampleWorkListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SampleWork.objects.none()
        return SampleWork.objects.filter(artist=self.request.user.artist_profile)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SampleWorkUploadSerializer
        return SampleWorkSerializer

    @extend_schema(
        tags=[Tags.ARTISTS],
        summary="Upload a sample work",
        description=(
            "Available to any artist, including one still `pending` approval — this is exactly "
            "what a pending artist uploads for review."
        ),
        request={"multipart/form-data": SampleWorkUploadSerializer},
        responses={201: SampleWorkSerializer, 400: Responses.VALIDATION_400},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        output = SampleWorkSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    delete=extend_schema(
        tags=[Tags.ARTISTS],
        summary="Delete a sample work",
        responses={404: Responses.NOT_FOUND_404},
    )
)
class SampleWorkDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]
    serializer_class = SampleWorkSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SampleWork.objects.none()
        return SampleWork.objects.filter(artist=self.request.user.artist_profile)

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()


@extend_schema_view(
    get=extend_schema(
        tags=[Tags.ARTISTS],
        summary="List an artist's sample works",
        description="Support/admin only — used during artist approval review.",
    )
)
class ArtistSampleWorkListView(generics.ListAPIView):
    serializer_class = SampleWorkSerializer
    permission_classes = [permissions.IsAuthenticated, IsSupportOrAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SampleWork.objects.none()
        return SampleWork.objects.filter(artist_id=self.kwargs["pk"])
