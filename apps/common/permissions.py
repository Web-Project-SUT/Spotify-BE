from rest_framework.permissions import SAFE_METHODS, BasePermission


class RolePermission(BasePermission):
    """Strategy base: subclasses declare which roles may pass."""

    allowed_roles: tuple[str, ...] = ()
    message = "Your role does not allow this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsListener(RolePermission):
    allowed_roles = ("listener",)


class IsArtist(RolePermission):
    allowed_roles = ("artist",)


class IsSupportOrAdmin(RolePermission):
    allowed_roles = ("support", "admin")


class IsAdmin(RolePermission):
    allowed_roles = ("admin",)


class IsListenerOrArtist(RolePermission):
    allowed_roles = ("listener", "artist")


class IsApprovedArtist(IsArtist):
    message = "Only approved artists may perform this action."

    def has_permission(self, request, view):
        return bool(super().has_permission(request, view) and request.user.status == "active")


class IsOwnerOrReadOnly(BasePermission):
    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return getattr(obj, self.owner_field, None) == request.user


class TierPermission(BasePermission):
    """Strategy base: subclasses declare which subscription tiers may pass."""

    allowed_tiers: tuple[str, ...] = ()
    message = "Your subscription tier does not allow this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.tier in self.allowed_tiers
        )


class IsSilverOrAbove(TierPermission):
    allowed_tiers = ("silver", "gold")
