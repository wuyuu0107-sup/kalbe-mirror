from django.urls import path
from . import views
from .sse import sse_subscribe

urlpatterns = [
    path("sse/subscribe", sse_subscribe, name="sse-subscribe"),
    path("list/", views.notification_list, name="notification-list"),
    path("mark-read/<int:notification_id>/", views.mark_notification_read, name="mark-notification-read"),
    path("mark-all-read/", views.mark_all_notifications_read, name="mark-all-read"),
    path("count/", views.notification_count, name="notification-count"),
]
