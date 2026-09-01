"""Tests for /system endpoints (offline KiCad path detection/configuration)."""

from __future__ import annotations


def test_kicad_check(client):
    response = client.get("/system/kicad-check")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_kicad_configure(client, tmp_path):
    symbol_dir = tmp_path / "symbols"
    symbol_dir.mkdir()

    response = client.post(
        "/system/kicad-configure",
        json={"symbol_path": str(symbol_dir), "footprint_path": "", "model_path": ""},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
