import os
from rest_framework import serializers
from save_to_database.models import CSV


class CSVFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    directory = serializers.SerializerMethodField()
    file_path = serializers.SerializerMethodField()  # Add for compatibility
    uploaded_at = serializers.SerializerMethodField()  # Map to created_at

    class Meta:
        model = CSV
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

    def get_file_path(self, obj):
        # Return the file field as file_path for compatibility
        return obj.file.name if obj.file else None

    def get_uploaded_at(self, obj):
        # Map created_at to uploaded_at
        return obj.created_at

    def get_file_url(self, obj):
        request = self.context.get("request")
        try:
            url = obj.file.url
        except ValueError:
            return None
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_filename(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None

    def get_size(self, obj):
        try:
            return obj.file.size
        except Exception:
            return None

    def get_directory(self, obj):
        if not obj.file or not obj.file.name:
            return ""
        path = obj.file.name
        # Assuming upload_to='datasets/csvs/', extract after 'datasets/csvs/' up to last '/'
        if path.startswith('datasets/csvs/'):
            relative_path = path[13:]  # Remove 'datasets/csvs/'
            directory = os.path.dirname(relative_path)
            return directory if directory else ""
        return ""
