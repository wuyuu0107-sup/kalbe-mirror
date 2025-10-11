from django.urls import path
from .views import CSVFileListCreateView, CSVFileRetrieveDestroyView, CSVFileDownloadView

urlpatterns = [
    path("files/", CSVFileListCreateView.as_view(), name="csvfile_list_create"),
    path("files/<int:pk>/", CSVFileRetrieveDestroyView.as_view(), name="csvfile_detail_destroy"),
    path("files/<int:pk>/download/", CSVFileDownloadView.as_view(), name="csvfile_download"),
]
