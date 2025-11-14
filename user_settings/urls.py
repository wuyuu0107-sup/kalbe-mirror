from django.urls import path
from . import views

app_name = 'user_settings'

urlpatterns = [
    path('change-password/', views.change_password, name='change_password'),
    path('profile/', views.user_profile, name='user_profile'),
    path('delete-account/', views.delete_account, name='delete_account'),
]