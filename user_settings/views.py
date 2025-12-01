import logging
import time
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
from .monitoring import (
    track_user_settings_transaction, 
    capture_user_event,
    UserSettingsSentryMonitor,
    UserSettingsOperationMonitor
)

logger = logging.getLogger(__name__)

_user_repository = DjangoUserRepository()
_password_service = PasswordChangeService(
    user_repository=_user_repository,
    password_encoder=DjangoPasswordEncoder(),
)

# Constants for error messages
AUTHENTICATION_REQUIRED = "Autentikasi diperlukan"
INVALID_PAYLOAD = "Payload tidak valid"

# Constants for monitoring categories
CATEGORY_VIEW = "user_settings.view"
CATEGORY_VALIDATION = "user_settings.validation"
CATEGORY_SERVICE = "user_settings.service"
CATEGORY_ERROR = "user_settings.error"


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
@track_user_settings_transaction("change_password")
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
    
    Monitoring:
    - Tracks execution time
    - Logs success/failure status
    - Records performance metrics in Sentry
    """
    operation_start = time.time()
    username = request.session.get('username', 'unknown')
    
    try:
        # Add breadcrumb for authentication check
        UserSettingsSentryMonitor.add_breadcrumb(
            "Checking user authentication",
            category=CATEGORY_VIEW,
            level="info"
        )
        
        # Check if user is authenticated
        user = get_authenticated_user(request)
        if not user:
            logger.warning(f"⚠️ Unauthorized password change attempt by session user: {username}")
            return JsonResponse({
                "error": AUTHENTICATION_REQUIRED,
                "message": "Anda harus login untuk mengubah password"
            }, status=401)

        # Set operation context with user details
        UserSettingsSentryMonitor.set_operation_context(
            operation="change_password",
            username=user.username,
            additional_data={"user_id": str(user.user_id)}
        )

        # Add breadcrumb for payload parsing
        UserSettingsSentryMonitor.add_breadcrumb(
            "Parsing request payload",
            category=CATEGORY_VIEW,
            level="info"
        )

        # Parse JSON payload
        data, error_response = parse_json_body(request)
        if error_response:
            logger.warning(f"⚠️ Invalid JSON payload for password change by user: {user.username}")
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
            logger.warning(f"⚠️ Missing required fields in password change: {missing_fields} for user: {user.username}")
            UserSettingsSentryMonitor.add_breadcrumb(
                "Validation failed - missing fields",
                category=CATEGORY_VALIDATION,
                level="warning",
                data={"missing_fields": missing_fields}
            )
            return JsonResponse({
                "error": "Field yang diperlukan tidak ada",
                "missing_fields": missing_fields,
                "message": f"Field berikut ini diperlukan: {', '.join(missing_fields)}"
            }, status=400)

        # Add breadcrumb for serializer validation
        UserSettingsSentryMonitor.add_breadcrumb(
            "Validating password change data",
            category=CATEGORY_VALIDATION,
            level="info"
        )

        # Initialize and validate the serializer
        serializer = ChangePasswordSerializer(user=user, data=data)
        
        if not serializer.is_valid():
            logger.warning(f"⚠️ Serializer validation failed for user: {user.username}")
            UserSettingsSentryMonitor.add_breadcrumb(
                "Serializer validation failed",
                category=CATEGORY_VALIDATION,
                level="warning",
                data={"errors": serializer.errors}
            )
            return JsonResponse({
                "error": "Validasi gagal",
                "validation_errors": serializer.errors,
                "message": "Silakan perbaiki kesalahan validasi dan coba lagi"
            }, status=400)

        # Add breadcrumb before service call
        UserSettingsSentryMonitor.add_breadcrumb(
            "Calling password change service",
            category=CATEGORY_SERVICE,
            level="info"
        )

        # Call password change service (this is also monitored internally)
        result = _password_service.change_password(
            user=user,
            new_password=serializer.cleaned_data["new_password"],
        )

        if not result.success:
            logger.error(f"❌ Password change service failed for user: {user.username}")
            return JsonResponse({
                "error": "Gagal mengubah password",
                "message": result.message,
            }, status=400)

        execution_time = time.time() - operation_start
        logger.info(f"✅ Password changed successfully for user: {user.username} in {execution_time:.3f}s")

        # Capture successful password change event in Sentry
        capture_user_event(
            event_name="password_changed",
            user_data={
                "username": user.username,
                "user_id": str(user.user_id)
            },
            extra_data={
                "success": True,
                "execution_time": execution_time
            }
        )

        return JsonResponse({
            "success": True,
            "message": result.message,
        }, status=200)

    except Exception as e:
        execution_time = time.time() - operation_start
        logger.error(
            f"❌ Error changing password for user {username}: {type(e).__name__}: {str(e)} "
            f"(after {execution_time:.3f}s)"
        )
        
        # Add error breadcrumb
        UserSettingsSentryMonitor.add_breadcrumb(
            "Unexpected error in password change",
            category=CATEGORY_ERROR,
            level="error",
            data={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "execution_time": execution_time
            }
        )
        
        return JsonResponse({
            "error": "Kesalahan server internal",
            "message": "Terjadi kesalahan yang tidak terduga. Silakan coba lagi nanti."
        }, status=500)


@track_user_settings_transaction("user_profile")
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
@track_user_settings_transaction("delete_account")
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
    
    Monitoring:
    - Tracks execution time
    - Logs success/failure status
    - Records account deletion events in Sentry
    """
    operation_start = time.time()
    username = request.session.get('username', 'unknown')
    
    try:
        # Add breadcrumb for authentication check
        UserSettingsSentryMonitor.add_breadcrumb(
            "Checking user authentication for account deletion",
            category=CATEGORY_VIEW,
            level="info"
        )
        
        # Check if user is authenticated
        user = get_authenticated_user(request)
        if not user:
            logger.warning(f"⚠️ Unauthorized account deletion attempt by session user: {username}")
            return JsonResponse({
                "error": AUTHENTICATION_REQUIRED,
                "message": "Anda harus login untuk menghapus akun"
            }, status=401)

        # Set operation context
        UserSettingsSentryMonitor.set_operation_context(
            operation="delete_account",
            username=user.username,
            additional_data={
                "user_id": str(user.user_id),
                "critical_operation": True
            }
        )

        # Add breadcrumb for payload parsing
        UserSettingsSentryMonitor.add_breadcrumb(
            "Parsing account deletion request",
            category=CATEGORY_VIEW,
            level="info"
        )

        # Parse JSON payload
        data, error_response = parse_json_body(request)
        if error_response:
            logger.warning(f"⚠️ Invalid JSON payload for account deletion by user: {user.username}")
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
            logger.warning(f"⚠️ Missing password in account deletion for user: {user.username}")
            UserSettingsSentryMonitor.add_breadcrumb(
                "Validation failed - missing password",
                category=CATEGORY_VALIDATION,
                level="warning"
            )
            return JsonResponse({
                "error": "Field yang diperlukan tidak ada",
                "message": "Password lama diperlukan"
            }, status=400)

        # Add breadcrumb for serializer validation
        UserSettingsSentryMonitor.add_breadcrumb(
            "Validating account deletion data",
            category=CATEGORY_VALIDATION,
            level="info"
        )

        # Initialize and validate the serializer
        serializer = DeleteAccountSerializer(user=user, data=data)
        
        if not serializer.is_valid():
            logger.warning(f"⚠️ Invalid password for account deletion by user: {user.username}")
            UserSettingsSentryMonitor.add_breadcrumb(
                "Password validation failed for account deletion",
                category=CATEGORY_VALIDATION,
                level="warning"
            )
            return JsonResponse({
                "error": "Validasi gagal",
                "validation_errors": serializer.errors,
                "message": "❌ Password salah"
            }, status=400)

        # Add breadcrumb before critical service call
        UserSettingsSentryMonitor.add_breadcrumb(
            "Calling account deletion service",
            category=CATEGORY_SERVICE,
            level="warning",  # Warning level for critical operation
            data={"username": user.username, "user_id": str(user.user_id)}
        )

        # Call account deletion service (this is also monitored internally)
        result = _password_service.delete_account(
            user=user,
            password=serializer.cleaned_data["current_password"],
        )

        if not result.success:
            logger.error(f"❌ Account deletion service failed for user: {user.username}")
            return JsonResponse({
                "error": "Gagal menghapus akun",
                "message": result.message,
            }, status=400)

        execution_time = time.time() - operation_start

        # Clear the session after successful deletion
        request.session.flush()

        logger.info(f"✅ Account deleted successfully for user: {user.username} in {execution_time:.3f}s")

        # Capture successful account deletion event in Sentry
        capture_user_event(
            event_name="account_deleted",
            user_data={
                "username": user.username,
                "user_id": str(user.user_id)
            },
            extra_data={
                "success": True,
                "execution_time": execution_time
            }
        )

        return JsonResponse({
            "success": True,
            "message": result.message,
        }, status=200)

    except Exception as e:
        execution_time = time.time() - operation_start
        logger.error(
            f"❌ Error deleting account for user {username}: {type(e).__name__}: {str(e)} "
            f"(after {execution_time:.3f}s)"
        )
        
        # Add error breadcrumb
        UserSettingsSentryMonitor.add_breadcrumb(
            "Unexpected error in account deletion",
            category=CATEGORY_ERROR,
            level="error",
            data={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "execution_time": execution_time
            }
        )
        
        return JsonResponse({
            "error": "Kesalahan server internal",
            "message": "Terjadi kesalahan yang tidak terduga. Silakan coba lagi nanti."
        }, status=500)
