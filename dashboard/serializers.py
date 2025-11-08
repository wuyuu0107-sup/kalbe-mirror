from rest_framework import serializers
from .models import ChatSuggestion


class ChatSuggestionSerializer(serializers.ModelSerializer):
    
    user = serializers.UUIDField(source='user.user_id', read_only=True)
    
    class Meta:
        model = ChatSuggestion
        fields = ['id', 'user', 'title', 'content', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']