import os
from rest_framework import serializers
from .models import CSVFile


class CSVFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    directory = serializers.SerializerMethodField()

    class Meta:
        model = CSVFile
        fields = [
            "id",
            "file_path",
            "file_url",
            "filename",
            "size",
            "directory",
            "uploaded_at",
        ]
        read_only_fields = ["file_url", "filename", "size", "directory", "uploaded_at", "id"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        try:
            url = obj.file_path.url
        except ValueError:
            return None
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_filename(self, obj):
        return os.path.basename(obj.file_path.name) if obj.file_path else None

    def get_size(self, obj):
        try:
            return obj.file_path.size
        except Exception:
            return None

    def get_directory(self, obj):
        if not obj.file_path or not obj.file_path.name:
            return ""
        path = obj.file_path.name
        # Assuming upload_to='csv_files/', extract after 'csv_files/' up to last '/'
        if path.startswith('csv_files/'):
            relative_path = path[9:]  # Remove 'csv_files/'
            directory = os.path.dirname(relative_path)
            return directory if directory else ""
        return ""
