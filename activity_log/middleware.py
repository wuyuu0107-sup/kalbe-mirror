from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest

class UserInRequestMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        """
        Adds the current user to the request object for logging purposes.
        """
        if not hasattr(request, 'user'):
            return
            
        request.user_for_logging = (
            request.user.username if request.user.is_authenticated else 'Anonymous'
        )
