import os
import shutil
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from .models import CSVFile
from .serializers import CSVFileSerializer
from .permissions import IsResearcherOnly


class CSVFileListCreateView(generics.ListCreateAPIView):
    queryset = CSVFile.objects.all().order_by("-uploaded_at")
    serializer_class = CSVFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsResearcherOnly]

    def create(self, request, *args, **kwargs):
        # require a file under key 'file'
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "No file provided under 'file' field."}, status=status.HTTP_400_BAD_REQUEST)
        instance = CSVFile.objects.create(file_path=uploaded_file)
        serializer = self.get_serializer(instance, context={"request": request})
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


class CSVFileRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = CSVFile.objects.all()
    serializer_class = CSVFileSerializer
    permission_classes = [IsResearcherOnly]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class CSVFileDownloadView(generics.GenericAPIView):
    permission_classes = [IsResearcherOnly]

    def get(self, request, pk):
        obj = get_object_or_404(CSVFile, pk=pk)
        try:
            file = obj.file_path.open("rb")
        except FileNotFoundError:
            raise Http404("File not found")
        response = FileResponse(file, as_attachment=True, filename=obj.filename)
        return response


class CSVFileMoveView(generics.GenericAPIView):
    permission_classes = [IsResearcherOnly]

    def post(self, request, pk):
        obj = get_object_or_404(CSVFile, pk=pk)
        target_dir = request.data.get('target_dir')
        if not target_dir:
            return Response({"detail": "target_dir is required."}, status=status.HTTP_400_BAD_REQUEST)
        filename = obj.filename
        new_path = f"csv_files/{target_dir}/{filename}"
        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'csv_files', target_dir)
        os.makedirs(full_target_dir, exist_ok=True)
        # Move file
        old_path = obj.file_path.path
        new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
        shutil.move(old_path, new_full_path)
        # Update DB
        obj.file_path.name = new_path
        obj.save()
        serializer = CSVFileSerializer(obj, context={'request': request})
        return Response(serializer.data)


class FolderMoveView(generics.GenericAPIView):
    permission_classes = [IsResearcherOnly]

    def post(self, request):
        source_dir = request.data.get('source_dir')
        target_dir = request.data.get('target_dir')
        if not source_dir or not target_dir:
            return Response({"detail": "source_dir and target_dir are required."}, status=status.HTTP_400_BAD_REQUEST)
        source_prefix = f"csv_files/{source_dir}/"
        files_to_move = CSVFile.objects.filter(file_path__startswith=source_prefix)
        if not files_to_move.exists():
            return Response({"detail": "No files found in source directory."}, status=status.HTTP_404_NOT_FOUND)
        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'csv_files', target_dir)
        os.makedirs(full_target_dir, exist_ok=True)
        moved_ids = []
        for obj in files_to_move:
            path = obj.file_path.name
            relative_path = path[len(source_prefix):]
            new_path = f"csv_files/{target_dir}/{relative_path}"
            # Move file
            old_full_path = obj.file_path.path
            new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
            # Ensure subdirs
            os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
            shutil.move(old_full_path, new_full_path)
            # Update DB
            obj.file_path.name = new_path
            obj.save()
            moved_ids.append(obj.id)
        return Response({"moved_files": moved_ids, "message": f"Moved {len(moved_ids)} files from {source_dir} to {target_dir}."})
