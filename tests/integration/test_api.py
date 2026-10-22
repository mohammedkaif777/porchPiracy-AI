"""Integration tests for the FastAPI API layer.

Uses TestClient, no real network, no sleeps.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend.models.event import Event


class TestHealth:
    """Health endpoint."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "porchpiracyai"


class TestSettings:
    """Settings endpoints."""

    def test_get_settings(self, client: TestClient) -> None:
        response = client.get("/settings")
        assert response.status_code == 200
        data = response.json()
        assert "protection_timeout_minutes" in data
        assert "loiter_threshold_seconds" in data

    def test_update_settings(self, client: TestClient) -> None:
        response = client.put("/settings", json={"loiter_threshold_seconds": 12.0})
        assert response.status_code == 200
        data = response.json()
        assert data["loiter_threshold_seconds"] == 12.0


class TestProtection:
    """Protection session lifecycle."""

    def test_status_returns_idle_when_no_session(self, client: TestClient) -> None:
        response = client.get("/protection/status")
        assert response.status_code == 200
        assert response.json()["state"] == "IDLE"

    def test_start_and_end_session(self, client: TestClient) -> None:
        start = client.post("/protection/start", json={})
        assert start.status_code == 201
        data = start.json()
        assert data["state"] in ("PACKAGE_DETECTED", "PROTECTION_ACTIVE")
        assert data["source"] == "MANUAL"

        end = client.post("/protection/end")
        assert end.status_code == 200
        assert end.json()["state"] == "PROTECTION_ENDED"

    def test_double_start_returns_409(self, client: TestClient) -> None:
        client.post("/protection/start", json={})
        second = client.post("/protection/start", json={})
        assert second.status_code == 409
        assert second.json()["code"] == "PROTECTION_ALREADY_ACTIVE"

    def test_end_without_session_returns_404(self, client: TestClient) -> None:
        response = client.post("/protection/end")
        assert response.status_code == 404
        assert response.json()["code"] == "NO_ACTIVE_PROTECTION"


class TestSimulateDelivery:
    """Simulated delivery endpoint."""

    def test_simulate_delivery(self, client: TestClient) -> None:
        response = client.post("/simulate/delivery", json={})
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "SIMULATED_DELIVERY"
        assert data["state"] == "PROTECTION_ACTIVE"

    def test_simulate_delivery_conflict(self, client: TestClient) -> None:
        client.post("/simulate/delivery", json={})
        second = client.post("/simulate/delivery", json={})
        assert second.status_code == 409


class TestEvents:
    """Event ingestion and listing."""

    def test_post_event(self, client: TestClient) -> None:
        # Start a session first.
        client.post("/simulate/delivery", json={})

        response = client.post(
            "/events",
            json={
                "type": "PERSON_APPROACHING",
                "timestamp_s": 1.0,
                "track_ids": {"person": 10},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "event" in data
        assert "threat_level" in data

    def test_list_events(self, client: TestClient) -> None:
        response = client.get("/events")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_video_filter_excludes_other_uploads_and_unlinked_events(
        self, client: TestClient, session: Session
    ) -> None:
        for event_id, video_id in (("selected", "video-a"), ("other", "video-b"), ("old", None)):
            session.add(
                Event(
                    event_id=event_id,
                    video_id=video_id,
                    type="PERSON_NEAR_PACKAGE",
                    timestamp_s=10.0,
                    confidence=0.9,
                )
            )
        session.commit()

        response = client.get("/events", params={"video_id": "video-a"})
        assert response.status_code == 200
        assert [event["event_id"] for event in response.json()] == ["selected"]
        assert client.get("/events", params={"video_id": "no-events"}).json() == []
        assert len(client.get("/events").json()) == 3


class TestIncidents:
    """Incident listing and review."""

    def test_list_incidents(self, client: TestClient) -> None:
        response = client.get("/incidents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestNotifications:
    """Notification listing."""

    def test_list_notifications(self, client: TestClient) -> None:
        response = client.get("/notifications")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestRingStatus:
    """Ring integration status."""

    def test_ring_status(self, client: TestClient) -> None:
        response = client.get("/ring/status")
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "local"
        assert data["simulated"] is True
