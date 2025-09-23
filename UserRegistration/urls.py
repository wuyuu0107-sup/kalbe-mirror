from django.urls import path
from UserRegistration.views import register_profile, verify_email

app_name = 'UserRegistration'

urlpatterns = [
   path("user/", register_profile, name="register"),
   path("verify-email/<uuid:token>/", verify_email, name="verify_email"),

]
