from rest_framework import serializers

class PredictRequestSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, f):
        name = (getattr(f, 'name', '') or '').lower()
        if not name.endswith('.csv'):
            raise serializers.ValidationError("Please upload a .csv file.")
        if f.size and f.size > 20 * 1024 * 1024:  # 20MB cap
            raise serializers.ValidationError("CSV too large (max 20MB).")
        return f
