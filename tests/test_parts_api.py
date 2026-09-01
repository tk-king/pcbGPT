"""Tests for /parts endpoints. Search, upload and reindex backends are mocked."""

from __future__ import annotations

import time

from backend.agent.tools.routers import parts as parts_router


def test_search_parts(client, monkeypatch):
    monkeypatch.setattr(
        parts_router,
        "search_components_paginated",
        lambda query, page, page_size, include_footprints: {
            "results": [{"id": "R_0402", "name": "R"}],
            "page": page,
            "page_size": page_size,
            "total": 1,
        },
    )
    response = client.get("/parts/search", params={"query": "resistor", "page": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["results"][0]["id"] == "R_0402"


def test_search_parts_failure(client, monkeypatch):
    def boom(query, page, page_size, include_footprints):
        raise RuntimeError("index corrupted")

    monkeypatch.setattr(parts_router, "search_components_paginated", boom)
    response = client.get("/parts/search", params={"query": "x"})
    assert response.status_code == 500
    assert "index corrupted" in response.json()["detail"]


def test_index_status(client, monkeypatch, tmp_path):
    from backend.data.Component.EmbeddingConfig import get_component_embedding_model
    import sys

    dataset_dir = tmp_path / "Datasets"
    dataset_dir.mkdir()
    (dataset_dir / "kicad_symbols.jsonl").write_text('{"a": 1}\n{"b": 2}\n')

    import backend.runtime_paths as runtime_paths

    monkeypatch.setattr(runtime_paths, "datasets_dir", lambda: dataset_dir)
    embedding_config = sys.modules["backend.data.Component.EmbeddingConfig"]
    monkeypatch.setattr(
        embedding_config, "get_component_embedding_model", lambda: "text-embedding-3-small"
    )

    response = client.get("/parts/index-status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["component_count"] == 2
    assert payload["symbol_index_exists"] is True
    assert payload["footprint_index_exists"] is False
    assert payload["embedding_model"] == "text-embedding-3-small"


def test_save_embedding_model(client, monkeypatch):
    import sys

    embedding_config = sys.modules["backend.data.Component.EmbeddingConfig"]
    monkeypatch.setattr(
        embedding_config,
        "save_component_embedding_model",
        lambda name: name.strip(),
    )
    response = client.post(
        "/parts/embedding-model", json={"embedding_model": " text-embedding-3-small "}
    )
    assert response.status_code == 200
    assert response.json()["embedding_model"] == "text-embedding-3-small"


def test_save_embedding_model_invalid(client, monkeypatch):
    import sys

    embedding_config = sys.modules["backend.data.Component.EmbeddingConfig"]

    def reject(name):
        raise ValueError("Unsupported embedding model")

    monkeypatch.setattr(embedding_config, "save_component_embedding_model", reject)
    response = client.post("/parts/embedding-model", json={"embedding_model": "bad"})
    assert response.status_code == 400


def test_reindex_job_lifecycle(client, monkeypatch):
    def fake_reindex(job_id, symbol_path, footprint_path, model_path, embedding_model):
        parts_router._set_reindex_progress(
            job_id,
            progress=100,
            message="Reindex complete",
            status="completed",
            result={"ok": True},
        )
        return {"ok": True}

    monkeypatch.setattr(parts_router, "_run_reindex_job", fake_reindex)

    queued = client.post("/parts/reindex", json={})
    assert queued.status_code == 200
    job_id = queued.json()["job_id"]
    assert queued.json()["status"] == "queued"

    for _ in range(50):
        status = client.get(f"/parts/reindex/{job_id}")
        assert status.status_code == 200
        if status.json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert status.json()["status"] == "completed"
    assert status.json()["result"] == {"ok": True}


def test_reindex_job_failure_is_reported(client, monkeypatch):
    def failing(job_id, *args):
        parts_router._set_reindex_progress(
            job_id,
            progress=100,
            message="Reindex failed",
            status="failed",
            error="no kicad",
        )
        parts_router._set_reindex_progress(
            job_id,
            progress=100,
            message="Reindex failed",
            status="failed",
            error="no kicad",
        )

    monkeypatch.setattr(parts_router, "_run_reindex_job", failing)

    queued = client.post("/parts/reindex", json={})
    job_id = queued.json()["job_id"]

    for _ in range(50):
        status = client.get(f"/parts/reindex/{job_id}").json()
        if status["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert status["status"] == "failed"
    assert status["error"] == "no kicad"


def test_reindex_status_unknown_job(client):
    response = client.get("/parts/reindex/missing-job")
    assert response.status_code == 404


def test_upload_part(client, monkeypatch):
    captured = {}

    def fake_install(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "symbol": kwargs["symbol_filename"]}

    monkeypatch.setattr(parts_router, "install_uploaded_part", fake_install)

    response = client.post(
        "/parts/upload",
        files={
            "kicad_sym": ("R.kicad_sym", b"(symbol)"),
            "kicad_mod": ("R.kicad_mod", b"(footprint)"),
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "symbol": "R.kicad_sym"}
    assert captured["symbol_bytes"] == b"(symbol)"
    assert captured["footprint_bytes"] == b"(footprint)"
    assert captured["step_bytes"] is None


def test_upload_part_empty_symbol_rejected(client):
    response = client.post(
        "/parts/upload",
        files={
            "kicad_sym": ("empty.kicad_sym", b""),
            "kicad_mod": ("R.kicad_mod", b"(footprint)"),
        },
    )
    assert response.status_code == 500
    assert "empty" in response.json()["detail"]
