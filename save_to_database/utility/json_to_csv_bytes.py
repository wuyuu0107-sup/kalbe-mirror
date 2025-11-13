import io
import csv
import json
import logging
from typing import Any, Dict, List, Union, Optional

# reuse existing flatten function
from csv_export.utility.json_to_csv import flatten_json

logger = logging.getLogger(__name__)

def json_to_csv_bytes(data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> bytes:
    """Convert JSON (list or dict) to CSV bytes using csv_export.utility.flatten_json."""
    if isinstance(data, dict):
        data = [data]
    if not data:
        return b""


    flat_rows = [flatten_json(item) for item in data]

    fieldnames = sorted({k for row in flat_rows for k in row.keys()})
    sio = io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in flat_rows:

        out = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else ("" if v is None else str(v)))
               for k, v in row.items()}

        for k in fieldnames:
            out.setdefault(k, "")
        writer.writerow(out)
    return sio.getvalue().encode("utf-8")
