from django.urls import path
from .views import CSVFileListCreateView, CSVFileRetrieveDestroyView, CSVFileDownloadView, CSVFileMoveView, FolderMoveView, FolderDeleteView

urlpatterns = [
    path("files/", CSVFileListCreateView.as_view(), name="csvfile_list_create"),
    path("files/<int:pk>/", CSVFileRetrieveDestroyView.as_view(), name="csvfile_detail_destroy"),
    path("files/<int:pk>/download/", CSVFileDownloadView.as_view(), name="csvfile_download"),
    path("files/<int:pk>/move/", CSVFileMoveView.as_view(), name="csvfile_move"),
    path("folders/move/", FolderMoveView.as_view(), name="folder_move"),
    path("folders/delete/", FolderDeleteView.as_view(), name="folder_delete"),
]
