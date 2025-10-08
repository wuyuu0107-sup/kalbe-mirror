from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import ChatSession, ChatMessage
from .service import answer_question
import json

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_session(req):
    s = ChatSession.objects.create(user_id=req.user.id, title=req.data.get("title",""))
    return Response({"id": str(s.id)}, status=201)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_message(req, sid):
    s = get_object_or_404(ChatSession, id=sid, user_id=req.user.id)
    m = ChatMessage.objects.create(session=s, role=req.data["role"], content=req.data["content"])
    return Response({"id": m.id}, status=201)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_messages(req, sid):
    s = get_object_or_404(ChatSession, id=sid, user_id=req.user.id)
    data = [{"role":m.role,"content":m.content,"ts":m.created_at.isoformat()}
            for m in s.messages.order_by("created_at")]
    return Response(data, status=200)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ask(req, sid):
    s = get_object_or_404(ChatSession, id=sid, user_id=req.user.id)
    q = req.data["question"]
    # persist user question
    ChatMessage.objects.create(session=s, role="user", content=q)

    try:
        answer = answer_question(q)
    except Exception as e:
        # jangan bocorkan detail; log internal kalau mau
        return Response({"error": "Failed to answer question"}, status=502)

    ChatMessage.objects.create(session=s, role="assistant", content=answer)
    return Response({"answer": answer}, status=200)
