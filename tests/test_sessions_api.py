"""Tests for /sessions endpoints (real sqlite store, isolated to a temp DB)."""

from __future__ import annotations

from tests.conftest import seeded_session  # noqa: F401


def test_get_session_not_found(client):
    response = client.get("/sessions/nope")
    assert response.status_code == 404


def test_get_session(client, seeded_session):
    response = client.get(f"/sessions/{seeded_session['session_id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == seeded_session["session_id"]
    assert payload["context"]["kicad_project_name"] == "my_project"
    assert payload["history"][0]["content"] == "hello"


def test_rename_session_title(client, seeded_session):
    session_id = seeded_session["session_id"]
    response = client.patch(f"/sessions/{session_id}/title", json={"title": "My title"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "My title"
    titles = {s["session_id"]: s["title"] for s in payload["sessions"]}
    assert titles[session_id] == "My title"


def test_rename_session_title_cleared(client, seeded_session):
    session_id = seeded_session["session_id"]
    response = client.patch(f"/sessions/{session_id}/title", json={"title": None})
    assert response.status_code == 200
    assert response.json()["title"] is None


def test_rename_session_not_found(client):
    response = client.patch("/sessions/nope/title", json={"title": "x"})
    assert response.status_code == 404


def test_delete_session(client, seeded_session):
    session_id = seeded_session["session_id"]
    response = client.delete(f"/sessions/{session_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert all(s["session_id"] != session_id for s in payload["sessions"])

    follow_up = client.get(f"/sessions/{session_id}")
    assert follow_up.status_code == 404


def test_delete_session_not_found(client):
    response = client.delete("/sessions/nope")
    assert response.status_code == 404
