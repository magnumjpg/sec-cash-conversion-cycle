"""Strict JSON writers: emit null, never NaN or Infinity.

Python's json module serialises non-finite floats as bare ``NaN`` / ``Infinity``
by default. Browsers, JavaScript, jq and other strict parsers reject those
tokens, so convert them to ``null`` at the boundary and pass
``allow_nan=False`` as a guard against a future non-finite value slipping
through.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def json_safe(obj: Any) -> Any:
    """Recursively convert non-finite floats (and NumPy scalars) for JSON."""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def write_json(path: str | Path, obj: Any, *, indent: int = 2,
               sort_keys: bool = False) -> None:
    """Write strict JSON, with non-finite numbers represented as null."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(json_safe(obj), indent=indent, ensure_ascii=False,
                      allow_nan=False, sort_keys=sort_keys)
    path.write_text(text, encoding="utf-8")
