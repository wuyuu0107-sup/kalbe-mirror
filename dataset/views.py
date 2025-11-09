import os
import shutil
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from save_to_database.models import CSV
from .serializers import CSVFileSerializer
from .permissions import IsResearcherOnly


class CSVFileListCreateView(generics.ListCreateAPIView):
    queryset = CSV.objects.all().order_by("-created_at")
    serializer_class = CSVFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsResearcherOnly]

    def create(self, request, *args, **kwargs):
        # require a file under key 'file'
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "No file provided under 'file' field."}, status=status.HTTP_400_BAD_REQUEST)
        name = os.path.splitext(uploaded_file.name)[0]
        instance = CSV.objects.create(name=name, file=uploaded_file, source_json=None)
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
    queryset = CSV.objects.all()
    serializer_class = CSVFileSerializer
    permission_classes = [IsResearcherOnly]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_destroy(self, instance):
        # Delete the file from storage before deleting the record
        if instance.file:
            storage = instance.file.storage
            name = instance.file.name
            if name:
                try:
                    storage.delete(name)
                except Exception:
                    # Ignore storage errors so delete doesn't crash
                    pass
        super().perform_destroy(instance)


class CSVFileDownloadView(generics.GenericAPIView):
    permission_classes = [IsResearcherOnly]

    def get(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        try:
            file = obj.file.open("rb")
        except FileNotFoundError:
            raise Http404("File not found")

        filename = os.path.basename(obj.file.name) if obj.file else "download.csv"
        response = FileResponse(file, as_attachment=True, filename=filename)
        return response


class CSVFileMoveView(generics.GenericAPIView):
    permission_classes = [IsResearcherOnly]

    def post(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        target_dir = request.data.get('target_dir')
        if not target_dir:
            return Response({"detail": "target_dir is required."}, status=status.HTTP_400_BAD_REQUEST)

        filename = os.path.basename(obj.file.name) if obj.file else "file.csv"
        new_path = f"datasets/csvs/{target_dir}/{filename}"
        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir)
        os.makedirs(full_target_dir, exist_ok=True)
        # Move file
        old_path = obj.file.path
        new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
        try:
            shutil.move(old_path, new_full_path)
        except Exception as e:
            return Response({"detail": f"Failed to move file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Update DB only if move succeeded
        obj.file.name = new_path
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
        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_move = CSV.objects.filter(file__startswith=source_prefix)
        if not files_to_move.exists():
            return Response({"detail": "No files found in source directory."}, status=status.HTTP_404_NOT_FOUND)
        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir)
        os.makedirs(full_target_dir, exist_ok=True)
        moved_ids = []
        for obj in files_to_move:
            path = obj.file.name
            relative_path = path[len(source_prefix):]
            new_path = f"datasets/csvs/{target_dir}/{relative_path}"
            # Move file
            old_full_path = obj.file.path
            new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
            # Ensure subdirs
            os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
            try:
                shutil.move(old_full_path, new_full_path)
            except Exception as e:
                # If move fails, skip this file and continue with others? Or fail the whole operation?
                # For now, fail the whole operation to maintain consistency
                return Response({"detail": f"Failed to move file {path}: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # Update DB only if move succeeded
            obj.file.name = new_path
            obj.save()
            moved_ids.append(obj.id)
        return Response({"moved_files": moved_ids, "message": f"Moved {len(moved_ids)} files from {source_dir} to {target_dir}."})
