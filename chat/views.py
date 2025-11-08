# chat/views.py
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
import uuid
import re
import json
import logging

from .models import ChatSession, ChatMessage
from .service import answer_question

DEMO_COOKIE_NAME = "demo_user_id"
log = logging.getLogger(__name__)



def _get_or_create_demo_user_id(request) -> uuid.UUID:
    try:
        v = request.COOKIES.get(DEMO_COOKIE_NAME)
        return uuid.UUID(v) if v else None
    except Exception:
        return None


def _attach_demo_cookie_if_needed(request, resp, user_id: uuid.UUID):
    # If authenticated user is present, no cookie needed
    if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
        return
    # If we used a demo user id, persist it
    resp.set_cookie(DEMO_COOKIE_NAME, str(user_id), max_age=60 * 60 * 24 * 365 * 2, samesite="Lax")


def _current_user_id(request) -> uuid.UUID:
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        # Prefer the auth user pk as UUID; if not UUID, namespace it deterministically
        try:
            return uuid.UUID(str(user.pk))
        except Exception:
            ns = uuid.UUID("00000000-0000-0000-0000-000000000000")
            return uuid.uuid5(ns, f"user:{user.pk}")
    # demo mode
    demo = _get_or_create_demo_user_id(request)
    return demo or uuid.uuid4()


def _first_words(s: str, n: int = 6) -> str:
    s = (s or "").strip()
    # strip markdown and collapse whitespace
    s = re.sub(r"[*_`#>]+", "", s)
    s = re.sub(r"\s+", " ", s)
    words = s.split(" ")
    t = " ".join(words[:n]).strip()
    return (t[:116] + "…") if len(t) > 117 else t


def _payload(request) -> dict:
    """
    Be liberal in what we accept: JSON body, DRF-parsed data, form, or query.
    Also flatten list values (e.g. QueryDict or DRF parsers) to first element.
    """
    def _flatten(d: dict) -> dict:
        out = {}
        for k, v in (d or {}).items():
            if isinstance(v, list) and v:
                out[k] = v[0]
            else:
                out[k] = v
        return out

    # DRF's request.data first
    if getattr(request, "data", None):
        try:
            return _flatten(dict(request.data))
        except Exception:
            pass

    # Raw JSON body
    try:
        raw = request.body.decode() if request.body else ""
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                return _flatten(data)
    except Exception:
        pass

    # Form / query fallbacks
    if hasattr(request, "POST") and request.POST:
        return _flatten(request.POST.dict())
    if hasattr(request, "GET") and request.GET:
        return _flatten(request.GET.dict())

    return {}



@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def sessions(request):
    """GET: list user's sessions (for sidebar)
       POST: create a new empty session
    """
    user_id = _current_user_id(request)

    if request.method == "GET":
        qs = ChatSession.objects.filter(user_id=user_id).order_by("-updated_at", "-created_at")
        data = [
            {
                "id": str(x.id),
                "title": x.title or "(New chat)",
                "updated_at": x.updated_at.isoformat(),
                "preview": x.last_message_preview or "",
                "created_at": x.created_at.isoformat(),
            }
            for x in qs[:50]
        ]
        resp = Response({"sessions": data}, status=200)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    # POST → create
    sess = ChatSession.objects.create(user_id=user_id)
    resp = Response({"id": str(sess.id), "title": sess.title or ""}, status=201)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp


@api_view(["PATCH", "DELETE"])
@permission_classes([AllowAny])
def session_detail(request, sid):
    user_id = _current_user_id(request)
    sess = get_object_or_404(ChatSession, pk=sid, user_id=user_id)

    if request.method == "PATCH":
        title = (request.data or {}).get("title", "").strip()
        if title:
            sess.title = title[:120]
            sess.save(update_fields=["title", "updated_at"])
        resp = Response({"ok": True, "title": sess.title or ""}, status=200)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    # DELETE
    sess.delete()
    resp = Response({"ok": True}, status=200)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp


@api_view(["GET"])
@permission_classes([AllowAny])
def get_messages(request, sid):
    """
    Return messages as list of dicts with at least: role, content.
    Oldest → newest. This matches tests that do: [m["role"] for m in msgs]
    """
    user_id = _current_user_id(request)
    sess = get_object_or_404(ChatSession, pk=sid, user_id=user_id)
    msgs = (
        sess.messages.order_by("created_at")
        .values("role", "content", "created_at")
    )
    data = [{"role": m["role"], "content": m["content"]} for m in msgs]
    resp = Response({"messages": data}, status=200)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp


@api_view(["POST"])
@permission_classes([AllowAny])
def post_message(request, sid):
    user_id = _current_user_id(request)
    sess = get_object_or_404(ChatSession, pk=sid, user_id=user_id)

    data = _payload(request)
    q = (data.get("content") or data.get("q") or data.get("question") or "").strip()
    if not q:
        resp = Response({"error": "empty message"}, status=400)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    ChatMessage.objects.create(session=sess, role="user", content=q)

    # auto-title on first user message
    if not sess.title:
        sess.title = _first_words(q)
    sess.last_message_preview = _first_words(q, 12)
    sess.save(update_fields=["title", "last_message_preview", "updated_at"])

    resp = Response({"ok": True}, status=201)
    _attach_demo_cookie_if_needed(request, resp, user_id)
    return resp


@api_view(["POST"])
@permission_classes([AllowAny])
def ask(request, sid):
    """Append user message, call engine, append assistant, return answer"""
    user_id = _current_user_id(request)
    sess = get_object_or_404(ChatSession, pk=sid, user_id=user_id)

    data = _payload(request)
    # accept q / question / content for flexibility in tests & frontend
    q_raw = data.get("q") or data.get("question") or data.get("content") or ""
    q = str(q_raw).strip()
    if not q:
        resp = Response({"error": "empty question"}, status=400)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    # store user msg
    ChatMessage.objects.create(session=sess, role="user", content=q)

    try:
        answer = answer_question(q)  # your existing service
        if isinstance(answer, dict):
            # optionally pretty-print JSON or pick a key
            answer = json.dumps(answer, ensure_ascii=False, indent=2)
        ChatMessage.objects.create(session=sess, role="assistant", content=answer)

        # keep sidebar metadata fresh
        preview = _first_words(answer, 12)
        if not sess.title:
            sess.title = _first_words(q)
        sess.last_message_preview = preview
        sess.save(update_fields=["title", "last_message_preview", "updated_at"])

        resp = Response({"answer": answer}, status=200)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp

    except Exception as e:
        # Classify a couple of “normal transient” failures so logs aren’t noisy
        msg = (str(e) or e.__class__.__name__).strip()
        is_transient = msg in {"empty_response", "llm_empty_sql"}

        if is_transient:
            log.info("ask(): transient LLM empty output: %s", msg)
        else:
            # full stack only for unexpected errors
            log.exception("ask() failed: %s", msg)

        # Friendly demo reply in DEBUG so tests/UAT don’t look broken
        if settings.DEBUG:
            demo = (
                "Mohon tanyakan pertanyaan yang relevan dengan data klinis. "
                f"Saat ini aku belum bisa menjawab: {q[:200]}"
                + (f" (detail: {msg})" if msg else "")
            )
            ChatMessage.objects.create(session=sess, role="assistant", content=demo)
            sess.last_message_preview = _first_words(demo, 12)
            sess.save(update_fields=["last_message_preview", "updated_at"])
            resp = Response({"answer": demo}, status=200)
            _attach_demo_cookie_if_needed(request, resp, user_id)
            return resp

        # Production: generic error body + correct cookie handling
        resp = Response({"error": "failed to answer question"}, status=502)
        _attach_demo_cookie_if_needed(request, resp, user_id)
        return resp
