
from django.contrib import admin
from django.urls import path, include
from authentication.views import protected_endpoint
from annotation.views_page import AnnotationTesterPage
from ocr.views import ocr_test_page
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('authentication.urls')),
    path('api/protected-endpoint/', protected_endpoint),
    path('ocr/', include('ocr.urls')),
    path('annotation/test/', AnnotationTesterPage.as_view(), name='annotation-test'),
    path('ocr_test_page/', ocr_test_page, name='ocr-test-page'),
    path('auth/', include('authentication.urls')),
    path('api/protected-endpoint/', protected_endpoint),
    path('', include('annotation.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
