from django.urls import path
from UserRegistration.views import *

app_name = 'UserRegistration'

urlpatterns = [
   path("user/", register_profile, name="register"),
]
