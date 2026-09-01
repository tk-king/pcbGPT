"""Tests for /sync endpoints. KiCad schematic parsing (import_kicad_folder) is mocked."""

from __future__ import annotations

from backend.agent.tools.app_state import _SESSION_CONTEXTS
from backend.agent.tools.routers import sync as sync_router
from backend.agent.tools.session_store import load_session


def _make_project_folder(tmp_path, with_schematic: bool):
    folder = tmp_path / "kicad_proj"
    folder.mkdir(exist_ok=True)
    if with_schematic:
        (folder / "main.kicad_sch").write_text("(kicad_sch)")
    return folder


def test_import_requires_folder_or_archive(client):
    response = client.post("/sync/import", json={"session_id": "s1"})
    assert response.status_code == 400
    assert "folder_path or archive_b64" in response.json()["detail"]


def test_import_missing_folder(client, tmp_path):
    response = client.post(
        "/sync/import",
        json={"session_id": "s1", "folder_path": str(tmp_path / "does-not-exist")},
    )
    assert response.status_code == 404


def test_import_output_only_folder(client, tmp_path):
    folder = _make_project_folder(tmp_path, with_schematic=False)
    session_id = "sess-sync-output"

    response = client.post(
        "/sync/import",
        json={"session_id": session_id, "folder_path": str(folder)},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "import_message" not in payload
    context = payload["context"]
    assert context["sync_mode"] == "output_only"
    assert context["kicad_project_path"] == str(folder)
    assert context["circuit"] is None

    # Context was persisted to the store.
    stored_context, stored_history = load_session(session_id)
    assert stored_context["sync_mode"] == "output_only"
    # No assistant import message for output-only folders.
    assert stored_history == []


def test_import_with_schematic(client, tmp_path, monkeypatch):
    folder = _make_project_folder(tmp_path, with_schematic=True)
    session_id = "sess-sync-import"

    def fake_import(kicad_folder, context):
        context.update(
            {
                "circuit": "circuit = Circuit()",
                "imported_netlist": "(netlist)",
                "kicad_project_name": kicad_folder.name,
            }
        )
        return context

    monkeypatch.setattr(sync_router, "import_kicad_folder", fake_import)

    response = client.post(
        "/sync/import",
        json={"session_id": session_id, "folder_path": str(folder), "folder_name": "ClientProj"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]["circuit"] == "circuit = Circuit()"
    assert payload["context"]["client_folder_name"] == "ClientProj"
    # The import message prefers the KiCad project name from the schematic.
    assert "Imported KiCad project" in payload["import_message"]
    assert "circuit is now in context" in payload["import_message"]

    stored_context, stored_history = load_session(session_id)
    roles = [m["role"] for m in stored_history]
    assert roles == ["assistant"]
    assert "Imported KiCad project" in stored_history[0]["content"]


def test_reimport_output_only_updates_context(client, tmp_path):
    folder = _make_project_folder(tmp_path, with_schematic=False)
    session_id = "sess-reimport-output"

    first = client.post(
        "/sync/import", json={"session_id": session_id, "folder_path": str(folder)}
    )
    assert first.status_code == 200

    second = client.post(
        "/sync/reimport", json={"session_id": session_id, "folder_path": str(folder)}
    )
    assert second.status_code == 200
    assert second.json()["context"]["sync_mode"] == "output_only"


def test_reimport_without_schematic_fails_for_new_session(client, tmp_path):
    folder = _make_project_folder(tmp_path, with_schematic=False)
    response = client.post(
        "/sync/reimport",
        json={"session_id": "sess-reimport-fresh", "folder_path": str(folder)},
    )
    assert response.status_code == 404
    assert "No .kicad_sch found" in response.json()["detail"]


def test_reimport_with_schematic(client, tmp_path, monkeypatch):
    folder = _make_project_folder(tmp_path, with_schematic=True)
    session_id = "sess-reimport-sch"

    def fake_import(kicad_folder, context):
        context["circuit"] = "circuit = Circuit()"
        return context

    monkeypatch.setattr(sync_router, "import_kicad_folder", fake_import)

    response = client.post(
        "/sync/reimport", json={"session_id": session_id, "folder_path": str(folder)}
    )
    assert response.status_code == 200
    assert "Imported KiCad project" in response.json()["import_message"]

    _, stored_history = load_session(session_id)
    assert any("Imported KiCad project" in (m.get("content") or "") for m in stored_history)


def test_local_folder_delegates_to_import(client, tmp_path):
    folder = _make_project_folder(tmp_path, with_schematic=False)
    session_id = "sess-local-folder"

    response = client.post(
        "/sync/local-folder",
        json={"session_id": session_id, "folder_path": str(folder)},
    )
    assert response.status_code == 200
    assert response.json()["context"]["sync_mode"] == "output_only"
    assert session_id in _SESSION_CONTEXTS


def test_import_from_archive_b64(client, tmp_path, monkeypatch):
    import base64
    import io
    import zipfile

    session_id = "sess-archive"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("proj/main.kicad_sch", "(kicad_sch)")

    extracted = tmp_path / "extracted"
    extracted.mkdir()

    monkeypatch.setattr(
        sync_router,
        "_extract_archive_to_workspace",
        lambda sid, archive: extracted,
    )

    response = client.post(
        "/sync/import",
        json={
            "session_id": session_id,
            "archive_b64": base64.b64encode(buffer.getvalue()).decode(),
        },
    )
    assert response.status_code == 200
    assert response.json()["context"]["sync_origin"] == "upload"
