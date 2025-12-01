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
from .utility.supabase_delete import delete_supabase_file


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


def match_existing_directory_case(target_dir: str) -> str:
    """
    Given a target directory like 'HELLO/world/track', attempt to match each
    path segment to existing directories recorded in the DB (case-insensitive)
    and return a new path where segments that already exist use the stored
    capitalization. If a segment does not exist at that level, it is kept as-is.

    This inspects `CSV.file` entries which store paths like
    'datasets/csvs/hello/World/file.csv' and derives folder names from them.
    """
    if not target_dir:
        return ''

    normalized = normalize_directory_path(target_dir)
    parts = normalized.split('/')

    adjusted_parts = []
    # start from the datasets/csvs root which is where CSV.file entries live
    current_prefix = 'datasets/csvs'

    for part in parts:
        search_prefix = current_prefix + '/'
        # get candidate file paths under this prefix
        qs = CSV.objects.filter(file__startswith=search_prefix).values_list('file', flat=True)
        if not qs.exists():
            # No existing entries under this prefix, keep remaining parts as-is
            adjusted_parts.extend(parts[len(adjusted_parts):])
            break

        # collect immediate child folder names under this prefix
        child_names = set()
        sp_len = len(search_prefix)
        for fp in qs:
            if len(fp) <= sp_len:
                continue
            remainder = fp[sp_len:]
            if '/' in remainder:
                child = remainder.split('/', 1)[0]
                if child:
                    child_names.add(child)

        if not child_names:
            # No subfolders under this prefix; keep remaining parts as-is
            adjusted_parts.extend(parts[len(adjusted_parts):])
            break

        # Try to find a case-insensitive match among child names
        match = None
        target_lower = part.lower()
        for child in child_names:
            if child.lower() == target_lower:
                match = child
                break

        if match:
            adjusted_parts.append(match)
            current_prefix = f"{current_prefix}/{match}"
        else:
            # No existing child matches case-insensitively; use provided segment
            adjusted_parts.append(part)
            current_prefix = f"{current_prefix}/{part}"

    return '/'.join(adjusted_parts)


class CSVFileListCreateView(generics.ListCreateAPIView):
    queryset = CSV.objects.all().order_by("-created_at")
    serializer_class = CSVFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticatedAndVerified]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
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
        # Attempt to delete the uploaded file from Supabase.
        try:
            delete_supabase_file(getattr(instance, "uploaded_url", None))
        except Exception:
            # Do not let Supabase deletion errors block record deletion
            pass
        super().perform_destroy(instance)


@method_decorator(csrf_exempt, name='dispatch')
class CSVFileMoveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticatedAndVerified]

    def post(self, request, pk):
        obj = get_object_or_404(CSV, pk=pk)
        target_dir = request.data.get('target_dir')
        if target_dir is None:
            return Response({"detail": "target_dir diperlukan."}, status=status.HTTP_400_BAD_REQUEST)

        target_dir = normalize_directory_path(target_dir)

        # Map target_dir segments to existing capitalization where possible
        adjusted_target_dir = match_existing_directory_case(target_dir)

        # Validate target_dir
        if not is_valid_path(target_dir):
            return Response({"detail": "target_dir tidak valid."}, status=status.HTTP_400_BAD_REQUEST)

        filename = os.path.basename(obj.file.name) if obj.file else "file.csv"
        new_path = f"datasets/csvs/{adjusted_target_dir}/{filename}" if adjusted_target_dir else f"datasets/csvs/{filename}"

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

        # We no longer perform local filesystem moves. Only update the stored path.
        # Supabase (or external storage) is responsible for actual file data.
        obj.file.name = new_path
        try:
            obj.save()
        except Exception as e:
            return Response({"detail": f"Gagal memperbarui path berkas: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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

        # Map target_dir segments to existing capitalization where possible
        adjusted_target_dir = match_existing_directory_case(target_dir)

        # Validate target_dir
        if not is_valid_path(target_dir):
            return Response({"detail": "target_dir tidak valid."}, status=status.HTTP_400_BAD_REQUEST)

        source_prefix = f"datasets/csvs/{source_dir}/"
        files_to_move = CSV.objects.filter(file__startswith=source_prefix)
        if not files_to_move.exists():
            return Response({"detail": "Tidak ada berkas yang ditemukan di direktori sumber."}, status=status.HTTP_404_NOT_FOUND)

        # Check for duplicate folder or file in target directory
        source_folder_name = os.path.basename(source_dir.rstrip('/'))
        new_folder_prefix = f"datasets/csvs/{adjusted_target_dir}/{source_folder_name}/" if adjusted_target_dir else f"datasets/csvs/{source_folder_name}/"

        # Check if a folder with the same name exists in the target directory (case-insensitive).
        # Exclude files that are part of the source directory (the ones being moved) so we don't
        # detect the moving folder itself as an existing folder in the target.
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__startswith=new_folder_prefix.lower()).exclude(file__startswith=source_prefix).exists():
            return Response({"detail": "Folder dengan nama ini sudah ada di direktori tujuan."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a file with the same name exists (exact match only, case-insensitive)
        # For a folder named "hello", check if file "datasets/csvs/.../hello" exists (without extension)
        # Do NOT match "hello.csv" - that's a different file
        new_file_path = f"datasets/csvs/{adjusted_target_dir}/{source_folder_name}" if adjusted_target_dir else f"datasets/csvs/{source_folder_name}"
        if CSV.objects.annotate(lower_file=Lower('file')).filter(lower_file__exact=new_file_path.lower()).exists():
            return Response({"detail": "Berkas dengan nama ini sudah ada di direktori tujuan."}, status=status.HTTP_400_BAD_REQUEST)

        # Only update DB paths; do not touch the filesystem.
        moved_ids = []
        for obj in files_to_move:
            path = obj.file.name
            relative_path = path[len(source_prefix):]
            new_path = f"datasets/csvs/{adjusted_target_dir}/{source_folder_name}/{relative_path}" if adjusted_target_dir else f"datasets/csvs/{source_folder_name}/{relative_path}"
            obj.file.name = new_path
            obj.save()
            moved_ids.append(obj.id)

        return Response({"moved_files": moved_ids, "message": f"Dipindahkan {len(moved_ids)} berkas dari {source_dir} ke {adjusted_target_dir}."})


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
            # Attempt to delete the uploaded file from Supabase.
            try:
                delete_supabase_file(getattr(obj, "uploaded_url", None))
            except Exception:
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
            stripped_dir = dir_path.rstrip('/\\')
            new_path = f"{stripped_dir}/{new_name}"
        else:
            new_path = f"datasets/csvs/{new_name}"

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

        # Do not rename a local file; just update the DB path
        obj.file.name = new_path
        try:
            obj.save()
        except Exception as e:
            return Response({"detail": f"Gagal memperbarui nama berkas: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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

        # Do not manipulate the filesystem. Update DB entries to reflect folder rename.
        files_to_update = CSV.objects.filter(file__startswith=source_prefix)
        updated_ids = []
        for obj in files_to_update:
            old_path = obj.file.name
            new_path = old_path.replace(source_prefix, new_folder_prefix, 1)
            obj.file.name = new_path
            obj.save()
            updated_ids.append(obj.id)

        return Response({"updated_files": updated_ids, "message": f"Folder diubah nama dari {source_dir} ke {new_name}."})
