from django.urls import path
from .views import PredictCsvView

app_name = 'predictions'
urlpatterns = [
    path('predict-csv/', PredictCsvView.as_view(), name='predict_csv'),
]
