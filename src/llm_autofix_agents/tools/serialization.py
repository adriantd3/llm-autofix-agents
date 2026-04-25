from __future__ import annotations

import json
from typing import Any


def json_result(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
