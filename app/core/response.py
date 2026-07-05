from datetime import datetime
from typing import Any

from fastapi.responses import Response


def _serialize(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


def _json_body(payload: dict) -> bytes:
    import json
    return json.dumps(_serialize(payload)).encode()


def ok(data: Any, status_code: int = 200, meta: dict | None = None) -> Response:
    body = _json_body({"success": True, "data": data, "error": None, "meta": meta or {}})
    return Response(content=body, status_code=status_code, media_type="application/json")


def created(data: Any, meta: dict | None = None) -> Response:
    return ok(data, status_code=201, meta=meta)


def accepted(data: Any, meta: dict | None = None) -> Response:
    return ok(data, status_code=202, meta=meta)
