"""Regression checks for uploaded-video event provenance."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend import api_client


def test_video_events_pass_video_filter(monkeypatch):
    monkeypatch.setattr(api_client, "_USE_MOCK", False)
    calls = []

    def get(path, params=None):
        calls.append((path, params))
        return [{"event_id": "detected"}]

    monkeypatch.setattr(api_client, "_get", get)
    assert api_client.get_events(video_id="upload") == [{"event_id": "detected"}]
    assert calls == [("/events", {"limit": 100, "video_id": "upload"})]


def test_backend_failure_cannot_show_sample_events_for_video(monkeypatch):
    monkeypatch.setattr(api_client, "_USE_MOCK", False)
    monkeypatch.setattr(api_client, "_FALLBACK_NOTICE", False)

    def unreachable(*args, **kwargs):
        raise api_client.requests.ConnectionError("offline")

    monkeypatch.setattr(api_client.requests, "request", unreachable)
    assert api_client.get_events(video_id="upload") == []
    assert api_client.using_mock()


def test_failed_upload_displays_error_and_scopes_events(monkeypatch):
    monkeypatch.setattr(api_client, "using_mock", lambda: False)
    monkeypatch.setattr(
        api_client,
        "get_videos",
        lambda **_kwargs: [
            {
                "video_id": "upload",
                "filename": "porch.mov",
                "status": "FAILED",
                "error": "OpenCV is missing",
            }
        ],
    )
    requests = []

    def events(**kwargs):
        requests.append(kwargs)
        return []

    monkeypatch.setattr(api_client, "get_events", events)
    page = Path(__file__).resolve().parents[2] / "frontend/pages/1_Live_Monitor.py"
    app = AppTest.from_file(str(page)).run()
    assert not app.exception
    assert [error.value for error in app.error] == ["OpenCV is missing"]
    assert "Retry analysis" in [button.label for button in app.button]
    assert requests == [{"limit": 50, "video_id": "upload"}]
    assert any("No detection events" in message.value for message in app.info)
