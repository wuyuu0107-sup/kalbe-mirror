from django.urls import path
from notification.sse import sse_subscribe

urlpatterns = [
    path("sse/subscribe", sse_subscribe, name="sse-subscribe"),
]
