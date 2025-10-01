# annotation/serializers.py
from rest_framework import serializers
from .models import Document, Patient, Annotation, Comment


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "source", "content_url", "payload_json", "meta", "created_at", "updated_at"]

    def validate(self, attrs):
        source = attrs.get("source", getattr(self.instance, "source", None))
        content_url = attrs.get("content_url", getattr(self.instance, "content_url", None))
        payload_json = attrs.get("payload_json", getattr(self.instance, "payload_json", None))

        if source == "pdf":
            # must have file URL (from upload) even if payload_json exists
            if not content_url:
                raise serializers.ValidationError({"content_url": "Required when source is 'pdf'."})
        elif source == "json":
            if payload_json in (None, ""):
                raise serializers.ValidationError({"payload_json": "Required when source is 'json'."})
        else:
            raise serializers.ValidationError({"source": "Must be 'pdf' or 'json'."})

        return attrs


# annotation/serializers.py
class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['id', 'name', 'external_id']


class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = ["id", "document", "patient", "label", "drawing_data", "created_at", "updated_at"]

    def validate_drawing_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("drawing_data must be a JSON object.")
        return value

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"
