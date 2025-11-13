# dashboard/nav.py
try:
    from annotation.models import Annotation
except ImportError:
    Annotation = None

# Human labels for known path segments
SEGMENT_LABELS = {
    "dashboard": "Dashboard",
    "files": "Files",
    "annotation": "Annotations",
    "viewer": "Viewer",            # ← add
    "ocr_test_page": "OCR",        # ← add
    "settings": "Settings",
    "new": "New",
    "edit": "Edit",
}

def looks_like_id(seg: str) -> bool:
    """Treat integers/uuids/hex-ish strings as IDs so we don't title-case them."""
    if seg.isdigit():
        return True
    s = seg.lower()
    return len(s) >= 8 and all(c in "0123456789abcdef-" for c in s)

# dashboard/nav.py (optional)
def try_label_annotation(pk: str) -> str | None:
    """Return a human-readable label for an Annotation if available."""
    try:
        if Annotation is None:
            return None

        obj = Annotation.objects.filter(pk=pk).only("id").first()
        if not obj:
            return None

        return getattr(obj, "title", None) or getattr(obj, "name", None) or f"#{obj.pk}"
    except Exception:
        return None