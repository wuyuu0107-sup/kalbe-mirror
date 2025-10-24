from datetime import datetime, MINYEAR
from ..storage import get_storage


def get_recent_files():
    storage = get_storage()
    items = list(storage.list_csv())

    norm = []
    for i in items:
        u = i.get("updated_at")
        if isinstance(u, str):
            u = datetime.fromisoformat(u.replace("Z", "+00:00")).replace(tzinfo=None)
        norm.append({**i, "updated_at": u})

    norm.sort(key=lambda x: x["updated_at"] or datetime(MINYEAR, 1, 1), reverse=True)
    return norm