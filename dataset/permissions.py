from rest_framework.permissions import BasePermission
from authentication.models import User as AuthUser


class IsResearcherOnly(BasePermission):
    """Researcher only permission using custom session auth and roles.

    A request is permitted when:
    - session contains 'user_id' and 'username'
    - a user exists with the same username
    - the session user_id matches that user's UUID
    - user.is_verified is True
    - 'researcher' is present in user's roles (case-insensitive match)
    """

    def has_permission(self, request, view):
        user_id = request.session.get("user_id")
        username = request.session.get("username")
        if not user_id or not username:
            return False
        try:
            user = AuthUser.objects.get(username=username)
        except AuthUser.DoesNotExist:
            return False
        if str(user.user_id) != str(user_id):
            return False
        if not getattr(user, "is_verified", False):
            return False
        roles = getattr(user, "roles", []) or []
        return any(str(r).lower() == "researcher" for r in roles)
