from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.permissions import (
    IsAdmin,
    IsApprovedArtist,
    IsArtist,
    IsListenerOrArtist,
    IsSupportOrAdmin,
)
from apps.common.quotas import AvatarUploadQuota
from apps.common.views import MediaResourceView

from . import services
from .models import AccountStatus, ArtistProfile, Follow, Notification, SampleWork, User
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    ArtistDetailSerializer,
    ArtistListSerializer,
    ArtistMeSerializer,
    ArtistRejectSerializer,
    AvatarUploadSerializer,
    CustomTokenObtainPairSerializer,
    MeUpdateSerializer,
    NotificationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PendingArtistSerializer,
    RegisterArtistSerializer,
    RegisterListenerSerializer,
    SampleWorkSerializer,
    SampleWorkUploadSerializer,
    UserMeSerializer,
    UserPreferencesSerializer,
    UserPublicSerializer,
)


def artist_profile_or_404(user):
    """`ensure_artist_profile` keeps every artist supplied with a profile, but a
    row predating that signal (or removed by hand) must read as "no such artist"
    rather than crash the view with `RelatedObjectDoesNotExist`."""
    try:
        return user.artist_profile
    except ArtistProfile.DoesNotExist as exc:
        raise Http404("This user has no artist profile.") from exc


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


class RegisterArtistView(generics.CreateAPIView):
    serializer_class = RegisterArtistSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = {"user": UserMeSerializer(user, context=self.get_serializer_context()).data}
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    pass


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {"type": "object", "properties": {"refresh": {"type": "string"}}}
        },
        responses={204: None},
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

    @extend_schema(request=PasswordResetRequestSerializer, responses={204: None})
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

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            uid = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):  # fmt: skip
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


class ArtistListView(generics.ListAPIView):
    serializer_class = ArtistListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            ArtistProfile.objects.filter(user__status=AccountStatus.ACTIVE)
            .select_related("user")
            .order_by("stage_name")
        )


class ArtistDetailView(generics.RetrieveAPIView):
    serializer_class = ArtistDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "pk"
    lookup_field = "user_id"

    def get_queryset(self):
        return ArtistProfile.objects.select_related("user")


class PendingArtistListView(generics.ListAPIView):
    """The artist-review queue: applications waiting on a support/admin decision."""

    serializer_class = PendingArtistSerializer
    permission_classes = [permissions.IsAuthenticated, IsSupportOrAdmin]

    def get_queryset(self):
        return (
            ArtistProfile.objects.filter(user__status=AccountStatus.PENDING)
            .select_related("user")
            .order_by("created_at")
        )


class ArtistApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupportOrAdmin]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, pk):
        profile = get_object_or_404(ArtistProfile, user_id=pk, user__status=AccountStatus.PENDING)
        now = timezone.now()
        profile.verified_at = now
        profile.reviewed_by = request.user
        profile.reviewed_at = now
        profile.save(update_fields=["verified_at", "reviewed_by", "reviewed_at"])
        profile.user.status = AccountStatus.ACTIVE
        profile.user.save(update_fields=["status"])
        services.notify(
            [profile.user],
            type=Notification.Type.APPROVAL,
            title="Artist account approved",
            message="You can now publish your work.",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtistRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSupportOrAdmin]

    def post(self, request, pk):
        profile = get_object_or_404(ArtistProfile, user_id=pk, user__status=AccountStatus.PENDING)
        serializer = ArtistRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        now = timezone.now()
        profile.rejection_reason = reason
        profile.reviewed_by = request.user
        profile.reviewed_at = now
        profile.save(update_fields=["rejection_reason", "reviewed_by", "reviewed_at"])
        profile.user.status = AccountStatus.REJECTED
        profile.user.save(update_fields=["status"])
        services.notify(
            [profile.user],
            type=Notification.Type.APPROVAL,
            title="Artist application rejected",
            message=f"Reason: {reason}",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtistMeView(generics.UpdateAPIView):
    serializer_class = ArtistMeSerializer
    permission_classes = [permissions.IsAuthenticated, IsApprovedArtist]

    def get_object(self):
        return artist_profile_or_404(self.request.user)


class UserListCreateView(generics.ListCreateAPIView):
    """The admin dashboard's Users tab: browse the roster and add an account.

    Admin-only — this is the one place emails and account statuses are listed,
    and the only way to hand out a role without going through the Django admin.
    """

    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    queryset = User.objects.order_by("-created_at")
    search_fields = ["email", "username", "display_name"]
    filterset_fields = ["role", "status"]
    ordering_fields = ["created_at", "email", "role"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return AdminUserSerializer

    @extend_schema(request=AdminUserCreateSerializer, responses={201: AdminUserSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output = AdminUserSerializer(user, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


@extend_schema_view(patch=extend_schema(responses={200: AdminUserSerializer}))
class UserDetailView(generics.RetrieveUpdateAPIView):
    """GET is the public profile card every signed-in user can read; PATCH is
    the admin-only role/status editor. PUT is excluded — there is no case for
    replacing a whole user record."""

    queryset = User.objects.all()
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return AdminUserUpdateSerializer
        return UserPublicSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(AdminUserSerializer(instance, context=self.get_serializer_context()).data)


class FollowView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsListenerOrArtist]

    @extend_schema(request=None, responses={201: None, 200: None, 400: None})
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

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        Follow.objects.filter(follower=request.user, following=target).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    put=extend_schema(
        request={"multipart/form-data": AvatarUploadSerializer}, responses={200: UserMeSerializer}
    ),
    delete=extend_schema(responses={204: None}),
)
class AvatarView(MediaResourceView):
    permission_classes = [permissions.IsAuthenticated]
    media_fields = ("avatar",)
    upload_serializer_class = AvatarUploadSerializer
    read_serializer_class = UserMeSerializer
    quota_class = AvatarUploadQuota

    def get_object(self):
        return self.request.user


class SampleWorkListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SampleWork.objects.none()
        return SampleWork.objects.filter(artist=artist_profile_or_404(self.request.user))

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SampleWorkUploadSerializer
        return SampleWorkSerializer

    @extend_schema(
        request={"multipart/form-data": SampleWorkUploadSerializer},
        responses={201: SampleWorkSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        output = SampleWorkSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class SampleWorkDeleteView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsArtist]
    serializer_class = SampleWorkSerializer

    def get_queryset(self):
        return SampleWork.objects.filter(artist=artist_profile_or_404(self.request.user))

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()


class ArtistSampleWorkListView(generics.ListAPIView):
    serializer_class = SampleWorkSerializer
    permission_classes = [permissions.IsAuthenticated, IsSupportOrAdmin]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SampleWork.objects.none()
        return SampleWork.objects.filter(artist_id=self.kwargs["pk"])


class NotificationListView(generics.ListAPIView):
    """The authenticated user's notifications, newest first."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return self.request.user.notifications.order_by("-created_at")


class NotificationMarkReadView(APIView):
    """Mark all of the user's notifications as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationItemReadView(APIView):
    """Mark a single one of the user's notifications as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        updated = request.user.notifications.filter(pk=pk).update(is_read=True)
        if not updated:
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationItemView(APIView):
    """Hide a single one of the user's notifications (deletes the row —
    a notification the user can never see again is indistinguishable from
    a deleted one, and it needs no extra "hidden" column)."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = request.user.notifications.filter(pk=pk).delete()
        if not deleted:
            raise Http404
        return Response(status=status.HTTP_204_NO_CONTENT)
