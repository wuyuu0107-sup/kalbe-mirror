# chat/service.py
from __future__ import annotations
import logging
import locale
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Protocol, Optional

# Adapters to existing modules (kept for backward compatibility)
from .sqlgen import generate_semantic_sql
from .repo import DB

log = logging.getLogger(__name__)
try:
    locale.setlocale(locale.LC_ALL, "")
except Exception:
    pass


# =========================
# Ports (Interfaces)
# =========================

class SQLGenerator(Protocol):
    def generate(self, user_message: str) -> str: ...


class QueryRunner(Protocol):
    def query(self, sql: str) -> Dict[str, Any]: ...


class AnswerFormatter(Protocol):
    def format(self, user_message: str, columns: List[str], rows: List[Tuple[Any, ...]]) -> str: ...


# =========================
# Adapters (to existing code)
# =========================

class DefaultSQLGenerator:
    """Adapter over existing generate_semantic_sql (kept as-is)."""
    def generate(self, user_message: str) -> str:
        return generate_semantic_sql(user_message)


class DBQueryRunner:
    """Adapter over repo.DB()."""
    def __init__(self, db: Optional[DB] = None) -> None:
        self._db = db or DB()

    def query(self, sql: str) -> Dict[str, Any]:
        return self._db.query(sql)


# =========================
# Formatting helpers (SRP)
# =========================

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
    # No rows at all
    if not rows:
        return "(empty)"

    # If columns are missing or empty, fall back to a bullet-style list
    if not cols or all((c is None or str(c).strip() == "") for c in cols):
        lines = []
        for row in rows[:max_rows]:
            # join non-empty cells, just in case
            txt = " | ".join(str(v) for v in row if str(v).strip() != "")
            if not txt:
                txt = "(empty row)"
            lines.append(f"- {txt}")
        if len(rows) > max_rows:
            lines.append(f"- ... ({len(rows) - max_rows} more)")
        return "\n".join(lines)

    # Normal Markdown table
    display_rows = rows[:max_rows]

    header = "| " + " | ".join(str(c).strip() for c in cols) + " |"
    separator = "| " + " | ".join("---" for _ in cols) + " |"
    body_lines = [
        "| " + " | ".join(str(cell).strip() for cell in row) + " |"
        for row in display_rows
    ]

    if len(rows) > max_rows:
        body_lines.append(f"| ... | ({len(rows) - max_rows} more rows) |")

    return "\n".join([header, separator] + body_lines)




# =========================
# Default formatter (SRP)
# =========================

@dataclass(frozen=True)
class DefaultAnswerFormatter:
    """Encapsulates all NL formatting rules used in the old module."""

    def _scalar_sentence(self, question: str, value: Any) -> str:
        n = _human_int(value)
        ql = question.lower()
        if ("how many" in ql or "berapa" in ql) and "patient" in ql:
            return f"There are {n} unique patient entries across all clinical trials."
        return f"The result is {n}."

    def _group_summary(self, question: str, cols: List[str], rows: List[Tuple[Any, ...]]) -> str:
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

    def _maybe_percentage_phrase(self, question: str, cols: List[str], rows: List[Tuple[Any, ...]]) -> str | None:
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

    def format(self, user_message: str, columns: List[str], rows: List[Tuple[Any, ...]]) -> str:
        # identical decision tree to previous implementation
        if not rows:
            return "No results found."

        pct = self._maybe_percentage_phrase(user_message, columns, rows)
        if pct:
            return pct

        if len(rows) == 1 and len(rows[0]) == 1:
            return self._scalar_sentence(user_message, rows[0][0])

        if len(columns) == 2:
            return self._group_summary(user_message, columns, rows)

        if 1 < len(columns) <= 5:
            table = _render_table(columns, rows, max_rows=8)
            return f"Found {len(rows)} rows.\n\n{table}"

        table = _render_table(columns, rows, max_rows=5)
        return f"Here are the results:\n\n{table}"


# =========================
# Application service (DIP)
# =========================

@dataclass
class SemanticQAService:
    """High-level orchestrator that depends on abstractions, not concretions."""
    sqlgen: SQLGenerator
    runner: QueryRunner
    formatter: AnswerFormatter

    def answer(self, user_message: str) -> str:

        # 1) NL -> SQL
        sql = self.sqlgen.generate(user_message)

        # 2) Execute
        result = self.runner.query(sql) or {}
        rows: List[Tuple[Any, ...]] = result.get("rows") or []
        cols: List[str] = result.get("columns") or []

        # 3) Format
        return self.formatter.format(user_message, cols, rows)


# =========================
# Public API (backward-compatible)
# =========================

def answer_question(user_message: str, session_id: str | None = None) -> str:
    """
    Fully semantic flow:
      NL -> SQL -> DB -> Natural language sentence/table.
    Always returns a STRING for views.py.
    session_id is accepted for compatibility (history inclusion can be added later).
    """
    text = (user_message or "").strip()
    if not text:
        return "Silakan ajukan pertanyaan terkait data klinis."

    msg = text.lower()
    if msg in {"hi", "hii", "hello", "hey", "halo", "hai"}:
        return (
            "Halo! 👋 Aku asisten yang fokus pada data klinis. "
            "Silakan tanyakan hal yang berkaitan dengan uji klinis atau dataset pasien."
        )

    service = SemanticQAService(
        sqlgen=DefaultSQLGenerator(),
        runner=DBQueryRunner(),
        formatter=DefaultAnswerFormatter(),
    )
    return service.answer(text, session_id=session_id)