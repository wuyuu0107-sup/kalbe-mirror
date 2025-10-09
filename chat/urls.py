from django.urls import path
from . import views
from django.views.generic import TemplateView
app_name = "chat"
urlpatterns = [
    path("sessions/", views.create_session, name="create_session"),
    path("sessions/<uuid:sid>/messages/", views.post_message, name="post_message"),
    path("sessions/<uuid:sid>/messages/list/", views.get_messages, name="get_messages"),
    path("sessions/<uuid:sid>/ask/", views.ask, name="ask"),
    path("demo/", TemplateView.as_view(template_name="chat/demo.html"), name="demo"),
]
