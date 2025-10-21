from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()

class SessionAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to set request.user based on session data.
    This ensures DRF's IsAuthenticated permission works with our custom User model.
    """
    def process_request(self, request):
        user_id = request.session.get('user_id')
        username = request.session.get('username')

        if user_id and username:
            try:
                user = User.objects.get(user_id=user_id, username=username)
                if user.is_authenticated:
                    request.user = user
                else:
                    request.user = AnonymousUser()
            except User.DoesNotExist:
                request.user = AnonymousUser()
        else:
            request.user = AnonymousUser()
