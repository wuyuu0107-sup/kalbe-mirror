from django.contrib import admin
from django.urls import path, include
from authentication.views import protected_endpoint
from annotation.views_page import AnnotationTesterPage
from ocr.views import ocr_test_page
from django.conf import settings
from django.conf.urls.static import static

# CSRF token endpoint (for SPA/Next.js to fetch a token)
from accounts.csrf import csrf as csrf_view

urlpatterns = [
    path("admin/", admin.site.urls),

    # CSRF endpoint used by the frontend: GET http://localhost:8000/api/csrf/
    path("api/csrf/", csrf_view),

    path("api/chat/", include("chat.urls")),

    # Accounts app routes (OTP request/confirm/test live under /accounts/…)
    path("accounts/", include("accounts.urls")),
    path('auth/', include('authentication.urls')),
    path('api/protected-endpoint/', protected_endpoint),
    path('ocr/', include('ocr.urls')),
    path('annotation/test/', AnnotationTesterPage.as_view(), name='annotation-test'),
    path('ocr_test_page/', ocr_test_page, name='ocr-test-page'),
    path('auth/', include('authentication.urls')),
    path('api/protected-endpoint/', protected_endpoint),
    path('', include('annotation.urls')),
    path('csv/', include('csv_export.urls')),
    path('save-to-database/', include('save_to_database.urls')),
    path('dataset/', include('dataset.urls')),
    path('dashboard/', include('dashboard.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
