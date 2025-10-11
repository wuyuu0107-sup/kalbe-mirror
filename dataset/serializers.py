import os
from rest_framework import serializers
from .models import CSVFile


class CSVFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()

    class Meta:
        model = CSVFile
        fields = [
            "id",
            "file_path",
            "file_url",
            "filename",
            "size",
            "uploaded_at",
        ]
        read_only_fields = ["file_url", "filename", "size", "uploaded_at", "id"]

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
