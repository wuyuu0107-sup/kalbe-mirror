from django.urls import path
from .views import PredictCsvView, PredictCsvDownloadView

app_name = 'predictions'
urlpatterns = [
    path('predict-csv/', PredictCsvView.as_view(), name='predict_csv'),
    path('predict-csv/download/<str:download_id>/', PredictCsvDownloadView.as_view(), name='predict_csv_download'),
]
