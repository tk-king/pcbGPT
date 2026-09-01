"""Smoke tests for the frontend-serving routes of the app."""

from __future__ import annotations


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200


def test_unknown_asset_returns_404(client):
    response = client.get("/this/does/not/exist.js")
    assert response.status_code == 404


def test_api_prefix_paths_are_not_served_as_frontend(client):
    response = client.get("/settings/nonexistent-sub-route")
    assert response.status_code in {404, 405}
