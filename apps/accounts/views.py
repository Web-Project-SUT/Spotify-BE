from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

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


class ArtistListView(generics.ListAPIView):
    serializer_class = ArtistListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ArtistProfile.objects.filter(user__status=AccountStatus.ACTIVE).select_related(
            "user"
        )


class ArtistDetailView(generics.RetrieveAPIView):
    serializer_class = ArtistDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "pk"
    lookup_field = "user_id"

    def get_queryset(self):
        return ArtistProfile.objects.select_related("user")


class ArtistMeView(generics.UpdateAPIView):
    serializer_class = ArtistMeSerializer
    permission_classes = [permissions.IsAuthenticated, IsApprovedArtist]

    def get_object(self):
        return self.request.user.artist_profile


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserPublicSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = User.objects.all()


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
        return SampleWork.objects.filter(artist=self.request.user.artist_profile)

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
        return SampleWork.objects.filter(artist=self.request.user.artist_profile)

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

    from .models import Notification
    from .serializers import NotificationSerializer

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
