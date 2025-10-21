from django.urls import path
from .views import ActivityViewSet

app_name = 'activity_log'

urlpatterns = [
    path('activities/', ActivityViewSet.as_view({'get': 'list'}), name='activity-list'),
]
