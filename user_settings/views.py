import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password
from django.db import transaction
from authentication.models import User
from authentication.helpers import parse_json_body
from .serializers import ChangePasswordSerializer

logger = logging.getLogger(__name__)


def get_authenticated_user(request):
    """
    Helper function to get the authenticated user from session.
    Returns the user object if authenticated, None otherwise.
    """
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    
    if not user_id or not username:
        return None
    
    try:
        user = User.objects.get(user_id=user_id, username=username)
        return user
    except User.DoesNotExist:
        return None


@csrf_exempt
@require_POST
def change_password(request):
    """
    API endpoint for authenticated users to change their password.
    
    Expected JSON payload:
    {
        "current_password": "current_password_here",
        "new_password": "new_strong_password",
        "confirm_password": "new_strong_password"
    }
    
    Returns:
    - 200: Password changed successfully
    - 400: Validation errors
    - 401: Unauthorized (not logged in)
    - 403: Current password incorrect
    - 500: Server error
    """
    try:
        # Check if user is authenticated
        user = get_authenticated_user(request)
        if not user:
            return JsonResponse({
                "error": "Authentication required",
                "message": "You must be logged in to change your password"
            }, status=401)

        # Parse JSON payload
        data, error_response = parse_json_body(request)
        if error_response:
            return error_response

        if data is None:
            return JsonResponse({
                "error": "Invalid payload",
                "message": "Request body must contain valid JSON"
            }, status=400)
        
        if not isinstance(data, dict):
            return JsonResponse({
                "error": "Invalid payload",
                "message": "Request body must be a JSON object"
            }, status=400)

        # Validate required fields
        required_fields = ['current_password', 'new_password', 'confirm_password']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                "error": "Missing required fields",
                "missing_fields": missing_fields,
                "message": f"The following fields are required: {', '.join(missing_fields)}"
            }, status=400)

        # Initialize and validate the serializer
        serializer = ChangePasswordSerializer(user=user, data=data)
        
        if not serializer.is_valid():
            return JsonResponse({
                "error": "Validation failed",
                "validation_errors": serializer.errors,
                "message": "Please fix the validation errors and try again"
            }, status=400)

        # Change password in database transaction
        with transaction.atomic():
            # Hash the new password
            new_password_hash = make_password(data['new_password'])
            
            # Update user password
            user.password = new_password_hash
            user.save(update_fields=['password'])
            
            logger.info(f"Password changed successfully for user: {user.username}")

        return JsonResponse({
            "success": True,
            "message": "Password changed successfully"
        }, status=200)

    except Exception as e:
        logger.error(f"Error changing password for user {request.session.get('username', 'unknown')}: {str(e)}")
        return JsonResponse({
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later."
        }, status=500)


def user_profile(request):
    """
    Get authenticated user profile information.
    This is a helper endpoint to get current user info.
    """
    if request.method != 'GET':
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({
            "error": "Authentication required",
            "message": "You must be logged in to view profile"
        }, status=401)
    
    return JsonResponse({
        "user_id": str(user.user_id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat(),
        "last_accessed": user.last_accessed.isoformat()
    }, status=200)
