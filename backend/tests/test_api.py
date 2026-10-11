from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_challenge_catalogue_work_without_docker() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["name"] == "RedPanda Labs"

        response = client.get("/api/challenges")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 15
        assert body["overall"]["completed"] == 0
        assert body["items"][0]["id"] == "challenge-01"


def test_dashboard_diagnostics_reports_docker_unavailable_honestly() -> None:
    with TestClient(app) as client:
        response = client.get("/api/diagnostics")
        assert response.status_code == 200
        payload = response.json()
        assert payload["docker"]["available"] is False
        assert payload["release_ready"] is False


def test_offline_hint_and_notebook_crud_are_real_api_operations() -> None:
    with TestClient(app) as client:
        hint_response = client.post("/api/challenges/challenge-01/hint")
        assert hint_response.status_code == 200
        assert hint_response.json()["hint_level"] == 1
        assert hint_response.json()["hint"]["content"]

        note_response = client.post("/api/notes", json={"title": "Test note", "content": "A useful concept", "tags": ["linux"]})
        assert note_response.status_code == 200
        note = note_response.json()
        assert note["kind"] == "note"

        explanation_response = client.post("/api/notes/explanations", json={"title": "Saved explanation", "content": "This stays separate", "tags": ["bash"]})
        assert explanation_response.status_code == 200
        assert explanation_response.json()["kind"] == "explanation"

        listing = client.get("/api/notes?q=useful")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        update = client.put(f"/api/notes/{note['id']}", json={"title": "Updated note", "content": "Updated content", "tags": ["linux", "paths"]})
        assert update.status_code == 200
        assert update.json()["title"] == "Updated note"

        deleted = client.delete(f"/api/notes/{note['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True


def test_starting_a_lab_returns_truthful_service_error_without_docker() -> None:
    with TestClient(app) as client:
        response = client.post("/api/challenges/challenge-01/start")
        assert response.status_code == 503
        assert "Docker" in response.json()["detail"]


def test_destructive_reset_needs_exact_confirmation() -> None:
    with TestClient(app) as client:
        response = client.post("/api/progress/reset", json={"confirmation": "yes"})
        assert response.status_code == 400
        assert "RESET ALL LEARNING PROGRESS" in response.json()["detail"]
