import os
import shutil
import re
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db.models.functions import Lower
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from save_to_database.models import CSV
from .serializers import CSVFileSerializer
from .permissions import IsAuthenticatedAndVerified


def is_valid_name(name):
    """
    Check if a file or folder name is valid.

    Rules enforced (cross-platform conservative):
    - Not empty, not exactly '.' or '..'
    - Must not contain the null byte
    - Must not contain path separators '/' or '\\'
    - Must not contain invalid Windows characters: <>:"/\\|?*
    - Must not end with a space or a period (Windows restriction)
    - Must not be a Windows reserved device name (CON, PRN, AUX, NUL, COM1..COM9, LPT1..LPT9)
      — including if an extension is present (e.g. CON.txt is invalid)
    - Names starting with '.' are allowed (hidden files on Unix)
    - Dots inside the name (like '..world') are allowed
    """
    if not name:
        return False

    # Disallow exactly current/parent directory
    if name in ('.', '..'):
        return False

    # Disallow null byte
    if '\x00' in name or '\0' in name:
        return False

    # Disallow path separators
    if '/' in name or '\\' in name:
        return False

    # Disallow Windows-invalid characters
    invalid_chars_re = re.compile(r'[<>:"/\\|?*]')
    if invalid_chars_re.search(name):
        return False

    # Disallow trailing space or dot (Windows restriction)
    if name.endswith(' ') or name.endswith('.'):
        return False

    # Reserved device names on Windows (case-insensitive)
    reserved = {'con', 'prn', 'aux', 'nul'}
    reserved.update({f'com{i}' for i in range(1, 10)})
    reserved.update({f'lpt{i}' for i in range(1, 10)})

    base = name.split('.', 1)[0].lower()  # check base name before extension
    if base in reserved:
        return False

    return True


def is_valid_path(path):
    """
    Check if a path is valid.

    - Empty path (root) is allowed
    - Split path on '/' or '\\', each component must be a valid name
    - Reject empty components (double slashes produce invalid empty names)
    """
    if not path:
        return True  # Empty path is ok for root

    # Normalize separators to '/' and strip only leading/trailing slashes
    parts = path.replace('\\', '/').strip('/').split('/')

    # Reject empty components
    if any(part == '' for part in parts):
        return False

    # Check each component
    for part in parts:
        if not is_valid_name(part):
            return False

    return True


def cleanup_orphaned_directory(directory_path):
    """
    If a directory exists on the physical filesystem but has no corresponding
    files in the database, delete it.
    """
    if os.path.exists(directory_path) and os.path.isdir(directory_path):
        try:
            shutil.rmtree(directory_path)
        except Exception:
            # If cleanup fails, continue anyway (not critical)
            pass


def normalize_directory_path(path):
    """
    Normalize a directory path by converting backslashes to forward slashes
    and stripping leading/trailing slashes.
    """
    if not path:
        return ''
    # Convert backslashes to forward slashes
    normalized = path.replace('\\', '/')
    # Strip leading and trailing slashes
    return normalized.strip('/')


class CSVFileListCreateView(generics.ListCreateAPIView):
    queryset = CSV.objects.all().order_by("-created_at")
    serializer_class = CSVFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticatedAndVerified]

    def create(self, request, *args, **kwargs):
        # require a file under key 'file'
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "Tidak ada berkas yang diberikan di bidang 'file'."}, status=status.HTTP_400_BAD_REQUEST)
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


@method_decorator(csrf_exempt, name='dispatch')
class CSVFileMoveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        target_dir = request.data.get('target_dir')
        if target_dir is None:
            return Response({"detail": "target_dir diperlukan."}, status=status.HTTP_400_BAD_REQUEST)

        target_dir = normalize_directory_path(target_dir)

        # Validate target_dir
        if not is_valid_path(target_dir):
            return Response({"detail": "target_dir tidak valid."}, status=status.HTTP_400_BAD_REQUEST)

        filename = os.path.basename(obj.file.name) if obj.file else "file.csv"
        new_path = f"datasets/csvs/{target_dir}/{filename}" if target_dir else f"datasets/csvs/{filename}"

        # Don't move if it's the same location
        if obj.file.name == new_path:
            serializer = CSVFileSerializer(obj, context={'request': request})
            return Response(serializer.data)

        # Check for duplicate file in target directory (case-insensitive)
        # Only check for exact match - file names must match completely including extension
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_path.lower()).exists():
            return Response({"detail": "Berkas dengan nama ini sudah ada di direktori tujuan."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a folder with the same name exists (case-insensitive).
        potential_folder_path = new_path.rstrip('/') + '/'  # do NOT strip extension
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=potential_folder_path.lower()).exists():
            return Response(
                {"detail": "Folder dengan nama ini sudah ada di direktori tujuan."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Clean up orphaned directory if it exists in physical files only
        orphaned_folder_path = os.path.join(settings.MEDIA_ROOT, new_path)
        cleanup_orphaned_directory(orphaned_folder_path)

        # Ensure target dir exists
        full_target_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir) if target_dir else os.path.join(settings.MEDIA_ROOT, 'datasets/csvs')
        os.makedirs(full_target_dir, exist_ok=True)

        # Move file
        old_path = obj.file.path
        new_full_path = os.path.join(settings.MEDIA_ROOT, new_path)
        try:
            shutil.move(old_path, new_full_path)
        except Exception as e:
            return Response({"detail": f"Gagal memindahkan berkas: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Update DB only if move succeeded
        obj.file.name = new_path
        obj.save()
        serializer = CSVFileSerializer(obj, context={'request': request})
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class FolderMoveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request):
        source_dir = request.data.get('source_dir')
        target_dir = request.data.get('target_dir')
        if source_dir is None or target_dir is None:
            return Response({"detail": "source_dir dan target_dir diperlukan."}, status=status.HTTP_400_BAD_REQUEST)

        source_dir = normalize_directory_path(source_dir)
        target_dir = normalize_directory_path(target_dir)

        # Validate target_dir
        if not is_valid_path(target_dir):
            return Response({"detail": "target_dir tidak valid."}, status=status.HTTP_400_BAD_REQUEST)

        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_move = CSV.objects.filter(file__startswith=source_prefix)
        if not files_to_move.exists():
            return Response({"detail": "Tidak ada berkas yang ditemukan di direktori sumber."}, status=status.HTTP_404_NOT_FOUND)

        # Check for duplicate folder or file in target directory
        source_folder_name = os.path.basename(source_dir.rstrip('/'))
        new_folder_prefix = f"datasets/csvs/{target_dir}/{source_folder_name}/" if target_dir else f"datasets/csvs/{source_folder_name}/"

        # Check if a folder with the same name exists in the target directory (case-insensitive).
        # Exclude files that are part of the source directory (the ones being moved) so we don't
        # detect the moving folder itself as an existing folder in the target.
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=new_folder_prefix.lower()).exclude(file__startswith=source_prefix).exists():
            return Response({"detail": "Folder dengan nama ini sudah ada di direktori tujuan."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a file with the same name exists (exact match only, case-insensitive)
        # For a folder named "hello", check if file "datasets/csvs/.../hello" exists (without extension)
        # Do NOT match "hello.csv" - that's a different file
        new_file_path = f"datasets/csvs/{target_dir}/{source_folder_name}" if target_dir else f"datasets/csvs/{source_folder_name}"
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_file_path.lower()).exists():
            return Response({"detail": "Berkas dengan nama ini sudah ada di direktori tujuan."}, status=status.HTTP_400_BAD_REQUEST)

        # Clean up orphaned directory if it exists in physical files only
        orphaned_folder_path = os.path.join(settings.MEDIA_ROOT, new_file_path)
        cleanup_orphaned_directory(orphaned_folder_path)

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
                return Response({"detail": f"Gagal memindahkan berkas {path}: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Update DB only if move succeeded
            obj.file.name = new_path
            obj.save()
            moved_ids.append(obj.id)

        return Response({"moved_files": moved_ids, "message": f"Dipindahkan {len(moved_ids)} berkas dari {source_dir} ke {target_dir}."})


class FolderDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def delete(self, request):
        source_dir = request.data.get('source_dir')
        if source_dir is None:
            return Response({"detail": "source_dir diperlukan."}, status=status.HTTP_400_BAD_REQUEST)

        source_dir = normalize_directory_path(source_dir)

        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_delete = CSV.objects.filter(file__startswith=source_prefix)
        if not files_to_delete.exists():
            return Response({"detail": "Tidak ada berkas yang ditemukan di direktori sumber."}, status=status.HTTP_404_NOT_FOUND)

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

        return Response({"deleted_files": deleted_ids, "message": f"Dihapus {len(deleted_ids)} berkas dari {source_dir}."})


@method_decorator(csrf_exempt, name='dispatch')
class CSVFileRenameView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        new_name = request.data.get('new_name')
        if not new_name:
            return Response({"detail": "new_name diperlukan."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate new_name
        if not is_valid_name(new_name):
            return Response({"detail": "new_name tidak valid."}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response({"detail": "Berkas dengan nama ini sudah ada di direktori."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if renaming would create a collision with a folder that has the same name
        potential_folder_path = new_path.rstrip('/') + '/'
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=potential_folder_path.lower()).exists():
            return Response(
                {"detail": "Folder dengan nama ini sudah ada di direktori."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Clean up orphaned directory if it exists in physical files only
        orphaned_folder_path = os.path.join(settings.MEDIA_ROOT, new_path)
        cleanup_orphaned_directory(orphaned_folder_path)

        current_full_path = obj.file.path
        dir_full_path = os.path.dirname(current_full_path)
        new_full_path = os.path.join(dir_full_path, new_name)

        try:
            os.rename(current_full_path, new_full_path)
        except FileNotFoundError:
            return Response({"detail": "Berkas sumber tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)
        except OSError as e:
            # Handle duplicate file errors at filesystem level
            if "file already exists" in str(e).lower() or "already exist" in str(e).lower():
                return Response({"detail": "Berkas dengan nama ini sudah ada di direktori."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"Gagal mengubah nama berkas: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"detail": f"Gagal mengubah nama berkas: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        obj.file.name = new_path
        obj.save()
        serializer = CSVFileSerializer(obj, context={'request': request})
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class FolderRenameView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request):
        source_dir = request.data.get('source_dir')
        new_name = request.data.get('new_name')
        if not source_dir or not new_name:
            return Response({"detail": "source_dir dan new_name diperlukan."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate new_name
        if not is_valid_name(new_name):
            return Response({"detail": "new_name tidak valid."}, status=status.HTTP_400_BAD_REQUEST)

        # Don't rename if it's the same name
        if source_dir == new_name:
            return Response({"updated_files": [], "message": f"Nama folder tidak berubah."})

        # full filesystem paths
        full_source_dir = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir)
        parent_dir = os.path.dirname(full_source_dir)
        full_target_dir = os.path.join(parent_dir, new_name)

        # Compute the parent-relative portion of the source_dir so we can
        # perform DB checks and updates scoped to the same parent (siblings only).
        # Use POSIX-like separators for the DB-stored file paths (they use '/').
        source_dir_norm = source_dir.rstrip('/\\')
        parent_rel = os.path.dirname(source_dir_norm)

        # Build DB prefixes that include the parent path when necessary so checks
        # are limited to the parent directory (siblings) rather than global.
        if parent_rel:
            new_folder_prefix = f"datasets/csvs/{parent_rel}/{new_name}/"
            new_file_path = f"datasets/csvs/{parent_rel}/{new_name}"
        else:
            new_folder_prefix = f"datasets/csvs/{new_name}/"
            new_file_path = f"datasets/csvs/{new_name}"

        source_prefix = f"datasets/csvs/{source_dir_norm}/"

        # Check for duplicate folder in parent directory (case-insensitive).
        # Exclude any files that are part of the source directory to avoid
        # detecting the folder being renamed as a conflict with itself.
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=new_folder_prefix.lower()).exclude(file__startswith=source_prefix).exists():
            return Response({"detail": "Folder dengan nama ini sudah ada di direktori."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a file with the same name exists in the same parent (exact match only, case-insensitive)
        # For a folder named "hello", check if file "datasets/csvs/.../hello" exists (without extension)
        # Do NOT match "hello.csv" - that's a different file
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_file_path.lower()).exists():
            return Response({"detail": "Berkas dengan nama ini sudah ada di direktori."}, status=status.HTTP_400_BAD_REQUEST)

        # Clean up orphaned directory if it exists in physical files only
        cleanup_orphaned_directory(full_target_dir)

        # Check if source directory exists
        if not os.path.exists(full_source_dir):
            return Response({"detail": "Direktori sumber tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)

        try:
            os.rename(full_source_dir, full_target_dir)
        except FileNotFoundError:
            return Response({"detail": "Direktori sumber tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)
        except OSError as e:
            # Handle duplicate directory errors at filesystem level
            if "file already exists" in str(e).lower() or "already exist" in str(e).lower():
                return Response({"detail": "Berkas atau folder dengan nama ini sudah ada di direktori."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"Gagal mengubah nama folder: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"detail": f"Gagal mengubah nama folder: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Use normalized source_prefix (parent-aware) when updating DB entries
        files_to_update = CSV.objects.filter(file__startswith=source_prefix)
        updated_ids = []
        for obj in files_to_update:
            old_path = obj.file.name
            # Replace only the source_prefix with the new folder prefix that preserves parent
            new_path = old_path.replace(source_prefix, new_folder_prefix, 1)
            obj.file.name = new_path
            obj.save()
            updated_ids.append(obj.id)

        return Response({"updated_files": updated_ids, "message": f"Folder diubah nama dari {source_dir} ke {new_name}."})
