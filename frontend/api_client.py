"""API client for the Streamlit dashboard.

When ``USE_MOCK=true``, or when the backend is unreachable, responses come from
``samples/mock_events.json`` so the dashboard still runs.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import requests

_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
_USE_MOCK = os.getenv("USE_MOCK", "false").lower() in {"true", "1", "yes"}
_MOCK_PATH = Path(__file__).resolve().parents[1] / "samples" / "mock_events.json"
_TIMEOUT = 10
_FALLBACK_NOTICE = False

_mock_protection: dict[str, Any] = {
    "session_id": None,
    "state": "IDLE",
    "source": None,
    "threat_level": "NONE",
    "seconds_remaining": None,
}


def using_mock() -> bool:
    """True when the dashboard is not talking to a live API."""
    return _USE_MOCK


def fallback_notice() -> bool:
    """True when mock mode was entered because the API was unreachable."""
    return _FALLBACK_NOTICE


def _url(path: str) -> str:
    return f"{_BACKEND_URL}{path}"


def _error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Request failed ({response.status_code})."
    if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
        return payload["detail"]
    return f"Request failed ({response.status_code})."


def _request(method: str, path: str, **kwargs: Any) -> Any:
    """HTTP helper that falls back to mock data when the API is down."""
    global _USE_MOCK, _FALLBACK_NOTICE
    if _USE_MOCK:
        return _mock_dispatch(method, path, kwargs.get("json"))
    try:
        response = requests.request(
            method,
            _url(path),
            timeout=kwargs.pop("timeout", _TIMEOUT),
            **kwargs,
        )
    except requests.RequestException:
        _USE_MOCK = True
        _FALLBACK_NOTICE = True
        return _mock_dispatch(method, path, kwargs.get("json"))
    if response.status_code >= 400:
        raise RuntimeError(_error_detail(response))
    if not response.content:
        return {}
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        return response.text
    return response.json()


def _get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def _post(path: str, json_body: dict | None = None) -> Any:
    return _request("POST", path, json=json_body or {})


def _put(path: str, json_body: dict | None = None) -> Any:
    return _request("PUT", path, json=json_body or {})


def get_health() -> dict:
    return _get("/health")


def get_protection_status() -> dict:
    return _get("/protection/status")


def start_protection(body: dict | None = None) -> dict:
    return _post("/protection/start", body or {})


def end_protection() -> dict:
    return _post("/protection/end")


def simulate_delivery(body: dict | None = None) -> dict:
    return _post("/simulate/delivery", body or {})


def get_events(
    session_id: str | None = None, limit: int = 100, video_id: str | None = None
) -> list[dict]:
    params: dict = {"limit": limit}
    if session_id:
        params["session_id"] = session_id
    if video_id:
        params["video_id"] = video_id
    result = _get("/events", params=params)
    if video_id and _USE_MOCK:
        # Sample events have no connection to an uploaded video.
        return []
    return result if isinstance(result, list) else []


def post_event(body: dict) -> dict:
    return _post("/events", body)


def get_incidents(session_id: str | None = None, limit: int = 100) -> list[dict]:
    params: dict = {"limit": limit}
    if session_id:
        params["session_id"] = session_id
    result = _get("/incidents", params=params)
    return result if isinstance(result, list) else []


def get_incident(incident_id: str) -> dict:
    return _get(f"/incidents/{incident_id}")


def review_incident(incident_id: str, status: str, note: str | None = None) -> dict:
    body: dict = {"status": status}
    if note:
        body["note"] = note
    return _post(f"/incidents/{incident_id}/review", body)


def get_report(incident_id: str) -> str:
    return _request("GET", f"/incidents/{incident_id}/report")


def get_settings() -> dict:
    return _get("/settings")


def update_settings(body: dict) -> dict:
    return _put("/settings", body)


def get_notifications(limit: int = 100) -> list[dict]:
    result = _get("/notifications", params={"limit": limit})
    return result if isinstance(result, list) else []


def get_ring_status() -> dict:
    return _get("/ring/status")


def upload_video(file_path: str) -> dict:
    return upload_video_bytes(Path(file_path).name, Path(file_path).read_bytes())


def upload_video_bytes(filename: str, data: bytes) -> dict:
    if _USE_MOCK:
        return {"video_id": str(uuid.uuid4()), "status": "UPLOADED", "filename": filename}
    try:
        response = requests.post(
            _url("/videos"),
            files={"file": (filename, data, "video/mp4")},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Backend is not reachable. Start it with `make api`.") from exc
    if response.status_code >= 400:
        raise RuntimeError(_error_detail(response))
    return response.json()


def analyze_video(video_id: str) -> dict:
    return _post(f"/videos/{video_id}/analyze")


def get_video_status(video_id: str) -> dict:
    return _get(f"/videos/{video_id}/status")


def get_videos(limit: int = 50) -> list[dict]:
    result = _get("/videos", params={"limit": limit})
    return result if isinstance(result, list) else []


def _load_mock_file() -> dict[str, Any]:
    if not _MOCK_PATH.is_file():
        return {"events": []}
    data = json.loads(_MOCK_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"events": data}
    return data if isinstance(data, dict) else {"events": []}


def _mock_dispatch(method: str, path: str, body: dict | None) -> Any:
    if method == "GET":
        return _mock_get(path)
    return _mock_post(path, body)


def _mock_get(path: str) -> Any:
    mock = _load_mock_file()
    if path == "/health":
        return {"status": "ok", "service": "porchpiracyai", "version": "0.1.0"}
    if path == "/protection/status":
        return dict(_mock_protection)
    if path == "/events":
        events = mock.get("events", [])
        return events[:20] if isinstance(events, list) else []
    if path == "/incidents":
        return mock.get("incidents") or []
    if path == "/notifications":
        return mock.get("notifications") or []
    if path == "/ring/status":
        return mock.get("ring_status") or {
            "mode": "local",
            "adapter": "LocalAdapter",
            "connected": True,
            "simulated": True,
            "capabilities": [
                {"name": "device_status", "supported": True, "simulated": True},
                {"name": "recent_events", "supported": True, "simulated": True},
            ],
            "device": {"name": "Front Door (Local Adapter)", "battery": 82, "signal": "good"},
            "message": "Running on the local development adapter. No Ring device is connected.",
        }
    if path == "/settings":
        return mock.get("settings") or {
            "protection_timeout_minutes": 360,
            "loiter_threshold_seconds": 8.0,
            "near_package_distance_px": 150.0,
            "frame_stride": 2,
            "detection_conf_threshold": 0.45,
            "incident_cooldown_seconds": 30.0,
            "ring_mode": "local",
            "llm_enabled": False,
        }
    if path.startswith("/videos"):
        return []
    if "/report" in path:
        return "<html><body><p>Mock evidence report. Potential package theft, for review.</p></body></html>"
    return {}


def _mock_post(path: str, body: dict | None = None) -> Any:
    del body
    if "/protection/start" in path or "/simulate/delivery" in path:
        source = "SIMULATED_DELIVERY" if "simulate" in path else "MANUAL"
        _mock_protection.update(
            {
                "session_id": str(uuid.uuid4()),
                "state": "PROTECTION_ACTIVE",
                "source": source,
                "threat_level": "NONE",
                "seconds_remaining": 360 * 60,
            }
        )
        return dict(_mock_protection)
    if "/protection/end" in path:
        _mock_protection.update(
            {"state": "PROTECTION_ENDED", "seconds_remaining": 0, "threat_level": "NONE"}
        )
        return {
            "state": "PROTECTION_ENDED",
            "session_id": _mock_protection.get("session_id") or "mock",
            "message": "Protection ended manually",
        }
    if path.endswith("/analyze") or "/analyze" in path:
        return {"status": "ANALYZING", "message": "Analysis started (mock)."}
    if path == "/events":
        return {"event": {}, "threat_level": "NONE", "incident_created": False, "incident": None}
    return {}
