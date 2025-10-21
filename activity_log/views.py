from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Activity
from .serializers import ActivitySerializer

class ActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        # Get last 50 activities by default
        queryset = self.get_queryset()[:50]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

def log_activity(user, activity_type, description, content_object=None):
    """
    Helper function to log an activity
    Args:
        user: User instance or user ID
        activity_type: Type of activity being logged
        description: Description of the activity
        content_object: Optional related object
    """
    # Handle both User instances and user IDs
    user_id = user.user_id if hasattr(user, 'user_id') else user

    activity = Activity.objects.create(
        user_id=user_id,
        activity_type=activity_type,
        description=description
    )
    if content_object:
        activity.content_object = content_object
        activity.save()
    return activity
