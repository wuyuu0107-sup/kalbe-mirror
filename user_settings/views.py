import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from authentication.helpers import parse_json_body
from .serializers import ChangePasswordSerializer, DeleteAccountSerializer
from .services.passwords import (
    DjangoPasswordEncoder,
    DjangoUserRepository,
    PasswordChangeService,
)

logger = logging.getLogger(__name__)

_user_repository = DjangoUserRepository()
_password_service = PasswordChangeService(
    user_repository=_user_repository,
    password_encoder=DjangoPasswordEncoder(),
)

AUTHENTICATION_REQUIRED = "Autentikasi diperlukan"
INVALID_PAYLOAD = "Payload tidak valid"


def get_authenticated_user(request):
    """
    Helper function to get the authenticated user from session.
    Returns the user object if authenticated, None otherwise.
    """
    user_id = request.session.get('user_id')
    username = request.session.get('username')
    
    if not user_id or not username:
        return None
    
    return _user_repository.get_by_credentials(user_id=str(user_id), username=username)


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
                "error": AUTHENTICATION_REQUIRED,
                "message": "Anda harus login untuk mengubah password"
            }, status=401)

        # Parse JSON payload
        data, error_response = parse_json_body(request)
        if error_response:
            return error_response

        if data is None:
            return JsonResponse({
                "error": INVALID_PAYLOAD,
                "message": "Request body harus berisi JSON yang valid"
            }, status=400)
        
        if not isinstance(data, dict):
            return JsonResponse({
                "error": INVALID_PAYLOAD,
                "message": "Request body harus berupa objek JSON"
            }, status=400)

        # Validate required fields
        required_fields = ['current_password', 'new_password', 'confirm_password']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                "error": "Field yang diperlukan tidak ada",
                "missing_fields": missing_fields,
                "message": f"Field berikut ini diperlukan: {', '.join(missing_fields)}"
            }, status=400)

        # Initialize and validate the serializer
        serializer = ChangePasswordSerializer(user=user, data=data)
        
        if not serializer.is_valid():
            return JsonResponse({
                "error": "Validasi gagal",
                "validation_errors": serializer.errors,
                "message": "Silakan perbaiki kesalahan validasi dan coba lagi"
            }, status=400)

        result = _password_service.change_password(
            user=user,
            new_password=serializer.cleaned_data["new_password"],
        )

        if not result.success:
            return JsonResponse({
                "error": "Gagal mengubah password",
                "message": result.message,
            }, status=400)

        logger.info("Password changed successfully for user: %s", user.username)

        return JsonResponse({
            "success": True,
            "message": result.message,
        }, status=200)

    except Exception as e:
        logger.error(f"Error changing password for user {request.session.get('username', 'unknown')}: {str(e)}")
        return JsonResponse({
            "error": "Kesalahan server internal",
            "message": "Terjadi kesalahan yang tidak terduga. Silakan coba lagi nanti."
        }, status=500)


def user_profile(request):
    """
    Get authenticated user profile information.
    This is a helper endpoint to get current user info.
    """
    if request.method != 'GET':
        return JsonResponse({"error": "Metode tidak diizinkan"}, status=405)
    
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({
            "error": AUTHENTICATION_REQUIRED,
            "message": "Anda harus login untuk melihat profil"
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


@csrf_exempt
@require_POST
def delete_account(request):
    """
    API endpoint for authenticated users to delete their account.
    
    Expected JSON payload:
    {
        "current_password": "current_password_here"
    }
    
    Returns:
    - 200: Account deleted successfully
    - 400: Validation errors
    - 401: Unauthorized (not logged in)
    - 500: Server error
    """
    try:
        # Check if user is authenticated
        user = get_authenticated_user(request)
        if not user:
            return JsonResponse({
                "error": AUTHENTICATION_REQUIRED,
                "message": "Anda harus login untuk menghapus akun"
            }, status=401)

        # Parse JSON payload
        data, error_response = parse_json_body(request)
        if error_response:
            return error_response

        if data is None:
            return JsonResponse({
                "error": INVALID_PAYLOAD,
                "message": "Request body harus berisi JSON yang valid"
            }, status=400)
        
        if not isinstance(data, dict):
            return JsonResponse({
                "error": INVALID_PAYLOAD,
                "message": "Request body harus berupa objek JSON"
            }, status=400)

        # Validate required fields
        if not data.get('current_password'):
            return JsonResponse({
                "error": "Field yang diperlukan tidak ada",
                "message": "Password lama diperlukan"
            }, status=400)

        # Initialize and validate the serializer
        serializer = DeleteAccountSerializer(user=user, data=data)
        
        if not serializer.is_valid():
            return JsonResponse({
                "error": "Validasi gagal",
                "validation_errors": serializer.errors,
                "message": "❌ Password salah"
            }, status=400)

        result = _password_service.delete_account(
            user=user,
            password=serializer.cleaned_data["current_password"],
        )

        if not result.success:
            return JsonResponse({
                "error": "Gagal menghapus akun",
                "message": result.message,
            }, status=400)

        # Clear the session after successful deletion
        request.session.flush()

        logger.info("Account deleted successfully for user: %s", user.username)

        return JsonResponse({
            "success": True,
            "message": result.message,
        }, status=200)

    except Exception as e:
        logger.error(f"Error deleting account for user {request.session.get('username', 'unknown')}: {str(e)}")
        return JsonResponse({
            "error": "Kesalahan server internal",
            "message": "Terjadi kesalahan yang tidak terduga. Silakan coba lagi nanti."
        }, status=500)
