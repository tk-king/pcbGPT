"""Tests for /settings endpoints. All provider HTTP calls are mocked."""

from __future__ import annotations

import backend.config as config_module
from tests.conftest import (
    MOCK_API_KEY,
    MOCK_BASE_URL,
    MOCK_MODEL_ID,
    MOCK_PROVIDER_NAME,
)


def test_get_settings(client):
    response = client.get("/settings")
    assert response.status_code == 200
    payload = response.json()
    for key in (
        "providers",
        "generation_model",
        "validation_model",
        "validation_enabled",
        "custom_providers",
        "custom_provider",
    ):
        assert key in payload


def test_save_system_settings_with_custom_provider_model(client, mock_provider):
    response = client.post(
        "/settings/system",
        json={"generation_model": f"{MOCK_PROVIDER_NAME}.{MOCK_MODEL_ID}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["generation_model"] == f"{MOCK_PROVIDER_NAME}.{MOCK_MODEL_ID}"
    assert payload["validation_enabled"] is False


def test_save_system_settings_unknown_model_rejected(client):
    response = client.post(
        "/settings/system",
        json={"generation_model": "doesnotexist.no-model"},
    )
    assert response.status_code == 400
    assert "Unsupported model" in response.json()["detail"]


def test_save_custom_provider_fetches_models(client, monkeypatch):
    async def fake_fetch(base_url, api_key=None):
        assert base_url == MOCK_BASE_URL
        assert api_key == MOCK_API_KEY
        return [{"id": MOCK_MODEL_ID, "name": "Mock Model"}]

    monkeypatch.setattr(config_module, "fetch_provider_models", fake_fetch)

    response = client.post(
        "/settings/custom-provider",
        json={
            "provider_name": "MockProvider",
            "base_url": MOCK_BASE_URL,
            "api_key": MOCK_API_KEY,
            "model_name": MOCK_MODEL_ID,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model_value"] == f"{MOCK_PROVIDER_NAME}.{MOCK_MODEL_ID}"
    names = {p["provider_name"] for p in payload["custom_providers"]}
    assert "mockprovider" in names
    custom = payload["custom_provider"]
    assert custom["provider_name"] == MOCK_PROVIDER_NAME
    assert custom["has_api_key"] is True
    assert custom["default_model"] == MOCK_MODEL_ID


def test_save_custom_provider_invalid_base_url(client, monkeypatch):
    async def fake_fetch(base_url, api_key=None):
        raise ValueError("Provider models lookup failed")

    monkeypatch.setattr(config_module, "fetch_provider_models", fake_fetch)

    response = client.post(
        "/settings/custom-provider",
        json={"provider_name": "Bad", "base_url": "not-a-url"},
    )
    assert response.status_code == 400


def test_refresh_provider_models(client, mock_provider, monkeypatch):
    async def fake_fetch(base_url, api_key=None):
        return [
            {"id": MOCK_MODEL_ID, "name": "Mock Model"},
            {"id": "new-model", "name": "New Model"},
        ]

    monkeypatch.setattr(config_module, "fetch_provider_models", fake_fetch)

    response = client.post(f"/settings/providers/{MOCK_PROVIDER_NAME}/refresh")
    assert response.status_code == 200
    payload = response.json()
    refreshed = next(
        p
        for p in payload["custom_providers"]
        if p["provider_name"] == MOCK_PROVIDER_NAME
    )
    model_ids = {m["id"] for m in refreshed["models"]}
    assert {"mock-model", "new-model"} <= model_ids


def test_refresh_provider_models_not_configured(client):
    response = client.post("/settings/providers/ghost/refresh")
    assert response.status_code == 404


def test_save_model_request_kwargs(client, mock_provider):
    response = client.post(
        "/settings/model-request-kwargs",
        json={
            "provider_name": MOCK_PROVIDER_NAME,
            "model_id": MOCK_MODEL_ID,
            "request_kwargs": {"temperature": 0.2},
        },
    )
    assert response.status_code == 200
    assert response.json()["custom_provider"]["provider_name"] == MOCK_PROVIDER_NAME


def test_save_model_request_kwargs_unknown_provider(client):
    response = client.post(
        "/settings/model-request-kwargs",
        json={
            "provider_name": "ghost",
            "model_id": "some-model",
            "request_kwargs": {},
        },
    )
    assert response.status_code == 400
