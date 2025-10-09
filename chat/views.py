# chat/views.py
from django.conf import settings 
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import uuid

from .models import ChatSession, ChatMessage          # <-- you were missing this
from .service import answer_question

DEMO_COOKIE_NAME = "demo_user_id"

def _get_user_id(request) -> uuid.UUID:
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        try:
            return uuid.UUID(str(user.id))
        except Exception:
            return uuid.uuid5(uuid.NAMESPACE_URL, f"user:{user.id}")
    raw = request.COOKIES.get(DEMO_COOKIE_NAME)
    try:
        return uuid.UUID(raw) if raw else uuid.uuid4()
    except Exception:
        return uuid.uuid4()

def _attach_demo_cookie_if_needed(request, response, user_id: uuid.UUID):
    user = getattr(request, "user", None)
    if not (user and getattr(user, "is_authenticated", False)):
        response.set_cookie(
            DEMO_COOKIE_NAME, str(user_id),
            samesite="Lax", httponly=False,  # demo only
        )

@csrf_exempt  # local demo only
@api_view(["POST"])
@permission_classes([AllowAny])
def create_session(request):
    user_id = _get_user_id(request)
    title = (request.data.get("title") or "Demo").strip()
    s = ChatSession.objects.create(user_id=user_id, title=title)
    resp = Response({"id": str(s.id)}, status=201)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def post_message(request, sid):
    user_id = _get_user_id(request)
    role = (request.data.get("role") or "").strip()
    content = (request.data.get("content") or "").strip()
    if role not in {"user", "assistant", "system"}:
        return Response({"error": "invalid role"}, status=400)
    if not content:
        return Response({"error": "content required"}, status=400)
    sess = get_object_or_404(ChatSession, id=sid, user_id=user_id)
    m = ChatMessage.objects.create(session=sess, role=role, content=content)
    resp = Response({"id": m.id}, status=201)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp

@api_view(["GET"])
@permission_classes([AllowAny])
def get_messages(request, sid):
    user_id = _get_user_id(request)
    sess = get_object_or_404(ChatSession, id=sid, user_id=user_id)
    data = [{"role": m.role, "content": m.content, "ts": m.created_at.isoformat()}
            for m in sess.messages.order_by("created_at")]
    resp = Response(data, status=200)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def ask(request, sid):
    user_id = _get_user_id(request)
    sess = get_object_or_404(ChatSession, id=sid, user_id=user_id)
    q = (request.data.get("question") or "").strip()
    if not q:
        resp = Response({"error": "question required"}, status=400)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    # persist user question
    ChatMessage.objects.create(session=sess, role="user", content=q)

    try:
        # Delegate to service layer for all questions.
        # answer_question now handles both domain-specific and general intents.
        answer = answer_question(q)

        # persist assistant answer and return JSON response
        ChatMessage.objects.create(session=sess, role="assistant", content=answer)
        resp = Response({"answer": answer}, status=200)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    except ValueError as ve:
        # client-side issue (unsupported / missing args)
        resp = Response({"error": str(ve)}, status=400)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    except Exception:
        # server-side issue (DB/SDK/network)
        if settings.DEBUG:
            demo = "[demo] Engine bermasalah. Echo: " + q[:200]
            ChatMessage.objects.create(session=sess, role="assistant", content=demo)
            resp = Response({"answer": demo}, status=200)
            _attach_demo_cookie_if_needed(request, resp, user_id)
            return resp
        resp = Response({"error": "failed to answer question"}, status=502)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp
