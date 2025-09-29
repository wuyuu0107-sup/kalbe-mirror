from rest_framework import serializers
from .models import Document, Patient, Annotation


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id','source','content_url','payload_json','meta','created_at','updated_at']

    def validate(self, attrs):
        payload_json = attrs.get('payload_json')
        if isinstance(payload_json, dict) and 'structured_data' in payload_json:
            attrs['payload_json'] = payload_json['structured_data']
            meta = attrs.get('meta') or {}
            meta.setdefault('wrapped_by', 'structured_data')
            attrs['meta'] = meta
        if not attrs.get('source') and attrs.get('payload_json'):
            attrs['source'] = 'json'
        if attrs.get('source') not in ('json','pdf'):
            raise serializers.ValidationError({'source': "must be 'json' or 'pdf'"})
        if not attrs.get('payload_json') and not attrs.get('content_url'):
            raise serializers.ValidationError("Provide 'payload_json' or 'content_url'.")
        if attrs.get('source') == 'pdf' and not attrs.get('content_url'):
            raise serializers.ValidationError({'content_url': "required when source='pdf'"})
        return attrs



class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['id', 'external_id', 'name']


class AnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Annotation
        fields = ['id', 'document', 'patient', 'label', 'drawing_data', 'created_at', 'updated_at']

    def validate(self, attrs):
        data = attrs.get('drawing_data')
        if data is None:
            raise serializers.ValidationError({'drawing_data': 'required'})
        if not isinstance(data, (dict, list)):
            raise serializers.ValidationError({'drawing_data': 'must be an object or array'})
        return attrs
