from django.urls import path
from . import views
from django.views.generic import TemplateView

app_name = "chat"

urlpatterns = [
    # Sessions
    path("sessions/", views.sessions, name="sessions"),                 # keep existing
    path("sessions/", views.sessions, name="create_session"),           # alias for tests

    # Session detail
    path("sessions/<uuid:sid>/", views.session_detail, name="session_detail"),

    # Messages
    path("sessions/<uuid:sid>/messages/", views.post_message, name="post_message"),
    path("sessions/<uuid:sid>/messages/list/", views.get_messages, name="get_messages"),   # keep existing
    path("sessions/<uuid:sid>/messages/list/", views.get_messages, name="messages_list"),  # alias for tests

    # Ask
    path("sessions/<uuid:sid>/ask/", views.ask, name="ask"),

    # Demo page
    path("demo/", TemplateView.as_view(template_name="chat/demo.html"), name="demo"),
]