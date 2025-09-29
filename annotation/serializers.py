# annotation/serializers.py
from rest_framework import serializers
from .models import Document, Patient, Annotation, Comment

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = "__all__"

class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = "__all__"

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"
