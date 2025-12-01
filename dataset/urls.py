from django.urls import path
<<<<<<< HEAD
from .views import CSVFileListCreateView, CSVFileRetrieveDestroyView, CSVFileDownloadView, CSVFileMoveView, FolderMoveView, FolderDeleteView, CSVFileRenameView, FolderRenameView
=======
from .views import CSVFileListCreateView, CSVFileRetrieveDestroyView, CSVFileMoveView, FolderMoveView, FolderDeleteView, CSVFileRenameView, FolderRenameView
>>>>>>> b92cae0a7ab2ee95c129c84afad7dc9c849b35c6

urlpatterns = [
    path("files/", CSVFileListCreateView.as_view(), name="csvfile_list_create"),
    path("files/<int:pk>/", CSVFileRetrieveDestroyView.as_view(), name="csvfile_detail_destroy"),
    path("files/<int:pk>/move/", CSVFileMoveView.as_view(), name="csvfile_move"),
    path("files/<int:pk>/rename/", CSVFileRenameView.as_view(), name="csvfile_rename"),
    path("folders/move/", FolderMoveView.as_view(), name="folder_move"),
    path("folders/delete/", FolderDeleteView.as_view(), name="folder_delete"),
    path("folders/rename/", FolderRenameView.as_view(), name="folder_rename"),
]
