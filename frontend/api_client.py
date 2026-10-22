"""API client for the Streamlit dashboard.

When ``USE_MOCK=true``, responses are generated from ``samples/mock_events.json``
so the dashboard works without a running backend.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
_USE_MOCK = os.getenv("USE_MOCK", "false").lower() in {"true", "1", "yes"}
_MOCK_PATH = Path(__file__).resolve().parents[1] / "samples" / "mock_events.json"
_TIMEOUT = 10


def _url(path: str) -> str:
    return f"{_BACKEND_URL}{path}"


def _get(path: str, params: dict | None = None) -> Any:
    """GET request to the backend."""
    if _USE_MOCK:
        return _mock_get(path)
    resp = requests.get(_url(path), params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json_body: dict | None = None) -> Any:
    """POST request to the backend."""
    if _USE_MOCK:
        return _mock_post(path, json_body)
    resp = requests.post(_url(path), json=json_body or {}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _put(path: str, json_body: dict | None = None) -> Any:
    """PUT request to the backend."""
    if _USE_MOCK:
        return {}
    resp = requests.put(_url(path), json=json_body or {}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# --- Public API ---


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


def get_events(session_id: str | None = None, limit: int = 100) -> list[dict]:
    params: dict = {"limit": limit}
    if session_id:
        params["session_id"] = session_id
    return _get("/events", params=params)


def post_event(body: dict) -> dict:
    return _post("/events", body)


def get_incidents(session_id: str | None = None, limit: int = 100) -> list[dict]:
    params: dict = {"limit": limit}
    if session_id:
        params["session_id"] = session_id
    return _get("/incidents", params=params)


def get_incident(incident_id: str) -> dict:
    return _get(f"/incidents/{incident_id}")


def review_incident(incident_id: str, status: str, note: str | None = None) -> dict:
    body: dict = {"status": status}
    if note:
        body["note"] = note
    return _post(f"/incidents/{incident_id}/review", body)


def get_settings() -> dict:
    return _get("/settings")


def update_settings(body: dict) -> dict:
    return _put("/settings", body)


def get_notifications(limit: int = 100) -> list[dict]:
    return _get("/notifications", params={"limit": limit})


def get_ring_status() -> dict:
    return _get("/ring/status")


def upload_video(file_path: str) -> dict:
    if _USE_MOCK:
        return {"video_id": "mock-video-001", "status": "UPLOADED", "filename": Path(file_path).name}
    with Path(file_path).open("rb") as f:
        resp = requests.post(
            _url("/videos"),
            files={"file": (Path(file_path).name, f, "video/mp4")},
            timeout=60,
        )
    resp.raise_for_status()
    return resp.json()


def analyze_video(video_id: str) -> dict:
    return _post(f"/videos/{video_id}/analyze")


def get_video_status(video_id: str) -> dict:
    return _get(f"/videos/{video_id}/status")


def get_videos(limit: int = 50) -> list[dict]:
    return _get("/videos", params={"limit": limit})


# --- Mock helpers ---


def _load_mock() -> list[dict]:
    if not _MOCK_PATH.is_file():
        return []
    data = json.loads(_MOCK_PATH.read_text(encoding="utf-8"))
    return data.get("events", data) if isinstance(data, dict) else data


def _mock_get(path: str) -> Any:
    if path == "/health":
        return {"status": "ok", "service": "porchpiracyai", "version": "0.1.0"}
    if path == "/protection/status":
        return {"state": "IDLE", "threat_level": "NONE"}
    if path == "/events":
        return _load_mock()[:20]
    if path == "/incidents":
        return []
    if path == "/notifications":
        return []
    if path == "/ring/status":
        return {
            "mode": "local", "adapter": "LocalAdapter", "connected": True,
            "simulated": True, "capabilities": [], "device": None,
            "message": "Running in mock mode.",
        }
    if path == "/settings":
        return {
            "protection_timeout_minutes": 360, "loiter_threshold_seconds": 8.0,
            "near_package_distance_px": 150.0, "frame_stride": 2,
            "detection_conf_threshold": 0.45, "incident_cooldown_seconds": 30.0,
            "ring_mode": "local", "llm_enabled": False,
        }
    if path.startswith("/videos"):
        return []
    return {}


def _mock_post(path: str, body: dict | None = None) -> Any:
    if "/protection/start" in path or "/simulate/delivery" in path:
        return {"state": "PACKAGE_DETECTED", "source": "SIMULATED_DELIVERY", "threat_level": "NONE"}
    if "/protection/end" in path:
        return {"state": "PROTECTION_ENDED", "session_id": "mock", "message": "Ended."}
    if path == "/events":
        return {"event": body, "threat_level": "NONE", "incident_created": False, "incident": None}
    return {}
