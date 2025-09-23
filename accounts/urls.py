from django.urls import path
from . import views

urlpatterns = [
    path("password-reset/request/", views.password_reset_request, name="password-reset-request"),
    path("password-reset/confirm/<uidb64>/<token>/", views.password_reset_confirm, name="password-reset-confirm"),
]
