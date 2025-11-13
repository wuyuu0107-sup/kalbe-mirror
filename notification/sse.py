import json
from queue import Queue
from threading import Lock
from typing import Dict, List
from django.http import StreamingHttpResponse, HttpResponseBadRequest
from django.utils.timezone import now

_clients: Dict[str, List[Queue]] = {}
_lock = Lock()

def _add_client(session_id, q):
    with _lock:
        _clients.setdefault(session_id, []).append(q)

def _remove_client(session_id, q):
    with _lock:
        arr = _clients.get(session_id, [])
        if q in arr:
            arr.remove(q)
        if not arr and session_id in _clients:
            _clients.pop(session_id, None)

def sse_subscribe(request):
    session_id = request.COOKIES.get("sessionid") or request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("session_id required")

    q = Queue()
    _add_client(session_id, q)

    def stream():
        try:
            yield "retry: 3000\n\n"
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        finally:
            _remove_client(session_id, q)

    resp = StreamingHttpResponse(stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    return resp

def sse_send(session_id: str, type_: str, *, data=None, job_id=None, user_id=None):
    """Enqueue a JSON event for all subscribers of a session."""
    payload = {
        "type": type_,
        "session_id": session_id,
        "job_id": job_id,
        "user_id": user_id,
        "created_at": now().isoformat(),
        "data": data or {},
    }
    encoded = json.dumps(payload)
    with _lock:
        for q in _clients.get(session_id, []):
            q.put(encoded)
