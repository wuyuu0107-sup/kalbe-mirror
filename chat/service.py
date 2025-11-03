# chat/service.py
from __future__ import annotations
import logging
import locale
from typing import Any, List, Tuple

from .sqlgen import generate_semantic_sql
from .repo import DB

log = logging.getLogger(__name__)
try:
    locale.setlocale(locale.LC_ALL, "")
except Exception:
    pass

def _human_int(v: Any) -> str:
    try:
        return locale.format_string("%d", int(v), grouping=True)
    except Exception:
        try:
            return f"{int(float(v)):,}"
        except Exception:
            return str(v)

def _human_pct(num: float, den: float) -> str:
    try:
        if float(den) == 0:
            return "0%"
        return f"{(float(num)/float(den))*100:.0f}%"
    except Exception:
        return "0%"

def _render_table(cols: List[str], rows: List[Tuple[Any, ...]], max_rows: int = 8) -> str:
    if not rows:
        return "(empty)"
    widths = [
        max(len(str(cols[i])), *(len(str(r[i])) for r in rows[:max_rows]))
        for i in range(len(cols))
    ]
    def fmt_row(r): return " | ".join(str(r[i]).ljust(widths[i]) for i in range(len(cols)))
    lines = [fmt_row(cols), "-+-".join("-" * w for w in widths)]
    for r in rows[:max_rows]:
        lines.append(fmt_row(r))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more)")
    return "\n".join(lines)

def _scalar_sentence(question: str, value: Any) -> str:
    n = _human_int(value)
    ql = question.lower()
    if ("how many" in ql or "berapa" in ql) and "patient" in ql:
        return f"There are {n} unique patient entries across all clinical trials."
    return f"The result is {n}."

def _group_summary(question: str, cols: List[str], rows: List[Tuple[Any, ...]]) -> str:
    if len(cols) == 2 and rows:
        try:
            idx_num = 1
            top = max(rows, key=lambda r: float(r[idx_num]))
            label = str(top[0])
            val = _human_int(top[idx_num])
            lowerq = question.lower()
            if any(k in lowerq for k in ("most", "highest", "terbanyak", "top")):
                lead = f"The {label} group has the highest value with {val}."
            else:
                lead = f"Top group: {label} with {val}."
        except Exception:
            lead = f"Found {len(rows)} groups."
        return f"{lead}\n\n{_render_table(cols, rows)}"
    return f"Found {len(rows)} rows.\n\n{_render_table(cols, rows)}"

def _maybe_percentage_phrase(question: str, cols: List[str], rows: List[Tuple[Any, ...]]) -> str | None:
    ql = question.lower()
    if not any(x in ql for x in ("percent", "percentage", "%", "persentase")):
        return None
    if len(rows) == 1 and len(rows[0]) == 2:
        a, b = rows[0]
        return f"There are {_human_int(a)} in the requested category, representing {_human_pct(a, b)} of {_human_int(b)} total."
    lc = [c.lower() for c in cols]
    if len(rows) == 1 and all(k in lc for k in ("female_count", "total_count")):
        a = rows[0][lc.index("female_count")]
        b = rows[0][lc.index("total_count")]
        return f"There are {_human_int(a)} female patients, representing {_human_pct(a, b)} of {_human_int(b)} participants."
    return None

# -------------------------
# Main entry
# -------------------------

def answer_question(user_message: str, session_id: str | None = None) -> str:
    """
    Fully semantic flow:
      NL -> SQL (generate_semantic_sql) -> DB -> Natural language sentence/table.
    Always returns a STRING for views.py.
    session_id is accepted for compatibility (history inclusion can be added later).
    """
    if "meaning of life" in user_message.lower():
        return ("I’m sorry, I can only assist with information about your clinical "
                "dataset and related analytics.")

    # 1) NL -> SQL
    sql = generate_semantic_sql(user_message)

    # 2) Execute
    db = DB()
    # DB.query is expected to return: {"rows": [...], "columns": [...]}
    result = db.query(sql)
    rows: List[Tuple[Any, ...]] = (result or {}).get("rows") or []
    cols: List[str] = (result or {}).get("columns") or []

    # 3) Format
    if not rows:
        return "No results found."

    pct = _maybe_percentage_phrase(user_message, cols, rows)
    if pct:
        return pct

    if len(rows) == 1 and len(rows[0]) == 1:
        return _scalar_sentence(user_message, rows[0][0])

    if len(cols) == 2:
        return _group_summary(user_message, cols, rows)

    if 1 < len(cols) <= 5:
        table = _render_table(cols, rows, max_rows=8)
        return f"Found {len(rows)} rows.\n\n{table}"

    table = _render_table(cols, rows, max_rows=5)
    return f"Here are the results:\n\n{table}"
