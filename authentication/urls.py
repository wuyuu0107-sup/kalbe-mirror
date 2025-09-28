from django.urls import path
from authentication.views import register_profile, login, verify_email

app_name = 'authentication'

urlpatterns = [
   path("register/", register_profile, name="register"),
   path("login/", login, name="login"),
   path("verify-email/<uuid:token>/", verify_email, name="verify_email"),
]