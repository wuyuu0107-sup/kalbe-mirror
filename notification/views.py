from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from .models import Notification
from authentication.models import User

@csrf_exempt
def get_authenticated_user(request):
    """Helper function to get authenticated user from session."""
    user_id = request.session.get('user_id')
    if not user_id:
        return None, JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        user = User.objects.get(user_id=user_id)
        return user, None
    except User.DoesNotExist:
        return None, JsonResponse({'error': 'User not found'}, status=404)

@csrf_exempt
def notification_list(request):
    """Get paginated list of notifications for the logged-in user."""
    user, error_response = get_authenticated_user(request)
    if error_response:
        return error_response

    notifications = Notification.objects.filter(user=user)
    page_number = request.GET.get('page', 1)
    paginator = Paginator(notifications, 20)  # 20 notifications per page
    page_obj = paginator.get_page(page_number)

    data = {
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.type,
                'type_display': n.get_type_display(),
                'created_at': n.created_at.isoformat(),
                'is_read': n.is_read,
                'job_id': n.job_id,
                'data': n.data,
            } for n in page_obj
        ],
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'total_count': paginator.count,
        }
    }
    return JsonResponse(data)

@csrf_exempt
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read."""
    user, error_response = get_authenticated_user(request)
    if error_response:
        return error_response

    notification = get_object_or_404(Notification, id=notification_id, user=user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})

@csrf_exempt
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the logged-in user."""
    user, error_response = get_authenticated_user(request)
    if error_response:
        return error_response

    Notification.objects.filter(user=user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success'})

@csrf_exempt
def notification_count(request):
    """Get count of unread notifications for the logged-in user."""
    user, error_response = get_authenticated_user(request)
    if error_response:
        return error_response

    count = Notification.objects.filter(user=user, is_read=False).count()
    return JsonResponse({'unread_count': count})
