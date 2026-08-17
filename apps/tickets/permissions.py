from rest_framework.permissions import BasePermission


class IsTicketParticipant(BasePermission):
    """The ticket's own author, or any support/admin account."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        return obj.author_id == user.id or user.role in ("support", "admin")
