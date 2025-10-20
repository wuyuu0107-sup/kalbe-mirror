from django.urls import path
from authentication.views import register_profile, login, verify_email, protected_endpoint, logout, verify_otp, resend_otp

app_name = 'authentication'

urlpatterns = [
   path("register/", register_profile, name="register"),
   path("login/", login, name="login"),
   path("logout/", logout, name="logout"),
   path("verify-email/<uuid:token>/", verify_email, name="verify_email"),
   path("verify-otp/", verify_otp, name="verify_otp"),
   path("resend-otp/", resend_otp, name="resend_otp"),
   path('api/protected-endpoint/', protected_endpoint, name='protected_endpoint'),
] 