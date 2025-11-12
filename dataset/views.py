import os
import shutil
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db.models.functions import Lower
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from save_to_database.models import CSV
from .serializers import CSVFileSerializer
from .permissions import IsAuthenticatedAndVerified


class CSVFileListCreateView(generics.ListCreateAPIView):
    queryset = CSV.objects.all().order_by("-created_at")
    serializer_class = CSVFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticatedAndVerified]

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
    permission_classes = [IsAuthenticatedAndVerified]

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
    permission_classes = [IsAuthenticatedAndVerified]

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
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        target_dir = request.data.get('target_dir')
        if target_dir is None:
            return Response({"detail": "target_dir is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Handle root directory
        if target_dir == '/':
            target_dir = ''

        filename = os.path.basename(obj.file.name) if obj.file else "file.csv"
        new_path = f"datasets/csvs/{target_dir}/{filename}" if target_dir else f"datasets/csvs/{filename}"

        # Don't move if it's the same location
        if obj.file.name == new_path:
            serializer = CSVFileSerializer(obj, context={'request': request})
            return Response(serializer.data)

        # Check for duplicate file in target directory (case-insensitive)
        # Only check for exact match - file names must match completely including extension
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_path.lower()).exists():
            return Response({"detail": "A file with this name already exists in the target directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a folder with the same name exists (case-insensitive).
        # For a file named "datasets/csvs/hello.csv", check if folder "datasets/csvs/hello/" exists
        base_no_ext = os.path.splitext(new_path)[0]
        potential_folder_path = base_no_ext.rstrip('/') + '/'
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=potential_folder_path.lower()).exists():
            return Response({"detail": "A folder with this name already exists in the target directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir) if target_dir else os.path.join(settings.MEDIA_ROOT, 'datasets/csvs')
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
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request):
        source_dir = request.data.get('source_dir')
        target_dir = request.data.get('target_dir')
        if source_dir is None or target_dir is None:
            return Response({"detail": "source_dir and target_dir are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Handle root directory
        if target_dir == '/':
            target_dir = ''

        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_move = CSV.objects.filter(file__startswith=source_prefix)
        if not files_to_move.exists():
            return Response({"detail": "No files found in source directory."}, status=status.HTTP_404_NOT_FOUND)

        # Check for duplicate folder or file in target directory
        source_folder_name = os.path.basename(source_dir.rstrip('/'))
        new_folder_prefix = f"datasets/csvs/{target_dir}/{source_folder_name}/" if target_dir else f"datasets/csvs/{source_folder_name}/"

        # Check if a folder with the same name exists in the target directory (case-insensitive).
        # Exclude files that are part of the source directory (the ones being moved) so we don't
        # detect the moving folder itself as an existing folder in the target.
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=new_folder_prefix.lower()).exclude(file__startswith=source_prefix).exists():
            return Response({"detail": "A folder with this name already exists in the target directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a file with the same name exists (exact match only, case-insensitive)
        # For a folder named "hello", check if file "datasets/csvs/.../hello" exists (without extension)
        # Do NOT match "hello.csv" - that's a different file
        new_file_path = f"datasets/csvs/{target_dir}/{source_folder_name}" if target_dir else f"datasets/csvs/{source_folder_name}"
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_file_path.lower()).exists():
            return Response({"detail": "A file with this name already exists in the target directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir) if target_dir else os.path.join(settings.MEDIA_ROOT, 'datasets/csvs')
        os.makedirs(full_target_dir, exist_ok=True)

        moved_ids = []
        for obj in files_to_move:
            path = obj.file.name
            relative_path = path[len(source_prefix):]
            new_path = f"datasets/csvs/{target_dir}/{source_folder_name}/{relative_path}" if target_dir else f"datasets/csvs/{source_folder_name}/{relative_path}"

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


class FolderDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def delete(self, request):
        source_dir = request.data.get('source_dir')
        if source_dir is None:
            return Response({"detail": "source_dir is required."}, status=status.HTTP_400_BAD_REQUEST)

        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_delete = CSV.objects.filter(file__startswith=source_prefix)
        if not files_to_delete.exists():
            return Response({"detail": "No files found in source directory."}, status=status.HTTP_404_NOT_FOUND)

        deleted_ids = []
        for obj in files_to_delete:
            # Delete the file from storage
            if obj.file:
                storage = obj.file.storage
                name = obj.file.name
                if name:
                    try:
                        storage.delete(name)
                    except Exception:
                        # Ignore storage errors so delete doesn't crash
                        pass
            # Delete the record
            obj_id = obj.id
            obj.delete()
            deleted_ids.append(obj_id)

        return Response({"deleted_files": deleted_ids, "message": f"Deleted {len(deleted_ids)} files from {source_dir}."})


class CSVFileRenameView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        new_name = request.data.get('new_name')
        if not new_name:
            return Response({"detail": "new_name is required."}, status=status.HTTP_400_BAD_REQUEST)

        current_path = obj.file.name
        dir_path = os.path.dirname(current_path)
        # Build storage name using POSIX style separators regardless of OS so it matches FileField naming
        if dir_path:
            new_path = f"{dir_path.rstrip('/\\')}/{new_name}"
        else:
            new_path = new_name

        # Don't rename if it's the same name
        if current_path == new_path:
            serializer = CSVFileSerializer(obj, context={'request': request})
            return Response(serializer.data)

        # Check for duplicate file in same directory (excluding current file, case-insensitive)
        # Only check for exact match - file names must match completely including extension
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_path.lower()).exclude(pk=obj.pk).exists():
            return Response({"detail": "A file with this name already exists in the directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if renaming would create a collision with a folder that has the same name (no extension)
        # e.g., cannot rename "hello.csv" to "hello" if folder "hello/" exists
        base_no_ext = os.path.splitext(new_path)[0]
        potential_folder_path = base_no_ext.rstrip('/') + '/'
        if new_path == base_no_ext and CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=potential_folder_path.lower()).exists():
            return Response({"detail": "A folder with this name already exists in the directory."}, status=status.HTTP_400_BAD_REQUEST)

        current_full_path = obj.file.path
        dir_full_path = os.path.dirname(current_full_path)
        new_full_path = os.path.join(dir_full_path, new_name)

        try:
            os.rename(current_full_path, new_full_path)
        except FileNotFoundError:
            return Response({"detail": "Source file not found."}, status=status.HTTP_404_NOT_FOUND)
        except OSError as e:
            # Handle duplicate file errors at filesystem level
            if "file already exists" in str(e).lower() or "already exist" in str(e).lower():
                return Response({"detail": "A file with this name already exists in the directory."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"Failed to rename file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"detail": f"Failed to rename file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        obj.file.name = new_path
        obj.save()
        serializer = CSVFileSerializer(obj, context={'request': request})
        return Response(serializer.data)


class FolderRenameView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request):
        source_dir = request.data.get('source_dir')
        new_name = request.data.get('new_name')
        if not source_dir or not new_name:
            return Response({"detail": "source_dir and new_name are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Don't rename if it's the same name
        if source_dir == new_name:
            return Response({"updated_files": [], "message": f"Folder name unchanged."})

        full_source_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir)
        parent_dir = os.path.dirname(full_source_dir)
        full_target_dir = os.path.join(parent_dir, new_name)

        # Check for duplicate folder in parent directory (case-insensitive)
        new_folder_prefix = f"datasets/csvs/{new_name}/"
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=new_folder_prefix.lower()).exists():
            return Response({"detail": "A folder with this name already exists in the directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a file with the same name exists (exact match only, case-insensitive)
        # For a folder named "hello", check if file "datasets/csvs/hello" exists (without extension)
        # Do NOT match "hello.csv" - that's a different file
        new_file_path = f"datasets/csvs/{new_name}"
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_file_path.lower()).exists():
            return Response({"detail": "A file with this name already exists in the directory."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if source directory exists
        if not os.path.exists(full_source_dir):
            return Response({"detail": "Source directory not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            os.rename(full_source_dir, full_target_dir)
        except FileNotFoundError:
            return Response({"detail": "Source directory not found."}, status=status.HTTP_404_NOT_FOUND)
        except OSError as e:
            # Handle duplicate directory errors at filesystem level
            if "file already exists" in str(e).lower() or "already exist" in str(e).lower():
                return Response({"detail": "A file or folder with this name already exists in the directory."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"Failed to rename folder: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"detail": f"Failed to rename folder: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_update = CSV.objects.filter(file__startswith=source_prefix)
        updated_ids = []
        for obj in files_to_update:
            old_path = obj.file.name
            new_path = old_path.replace(source_prefix, f"datasets/csvs/{new_name}/", 1)
            obj.file.name = new_path
            obj.save()
            updated_ids.append(obj.id)

        return Response({"updated_files": updated_ids, "message": f"Renamed folder from {source_dir} to {new_name}."})
