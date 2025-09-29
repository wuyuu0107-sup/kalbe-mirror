"""
URL configuration for kalbe_be project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path, include
from authentication.views import protected_endpoint
from ocr.views import api_ocr
from annotation.views_page import AnnotationTesterPage
from ocr.views import ocr_test_page

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('annotation.urls')),
    # Direct API endpoint for OCR (avoid nesting include which caused
    # requests to /api/ocr/ to resolve to the ocr_test_page view).
    path('api/ocr/', api_ocr),
    # UI and other OCR routes live under /ocr/
    path('ocr/', include('ocr.urls')),
    path('annotation/test/', AnnotationTesterPage.as_view(), name='annotation-test'),
    path('ocr_test_page/', ocr_test_page, name='ocr-test-page'),
    path('auth/', include('authentication.urls')),
    path('api/protected-endpoint/', protected_endpoint),
]
