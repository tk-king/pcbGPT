"""Tests for /download endpoints. Circuit-code execution and KiCad generation are mocked."""

from __future__ import annotations

import zipfile
from io import BytesIO

from backend.agent.tools.app_state import _SESSION_CONTEXTS
from backend.agent.tools.routers import downloads as downloads_router


def test_download_netlist_unknown_session(client):
    response = client.get("/download/netlist/ghost")
    assert response.status_code == 404


def test_download_netlist_without_circuit(client):
    _SESSION_CONTEXTS["sess-nonet"] = {"circuit": None}
    response = client.get("/download/netlist/sess-nonet")
    assert response.status_code == 404
    assert "generate a schematic" in response.json()["detail"]


def test_download_netlist_success(client, monkeypatch):
    _SESSION_CONTEXTS["abcdefgh1234"] = {"circuit": "circuit = Circuit()"}
    monkeypatch.setattr(
        downloads_router,
        "convert_code_to_netlist",
        lambda code: "* circuit netlist v2\nR1 N1 N2 1k\n",
    )

    response = client.get("/download/netlist/abcdefgh1234")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "attachment" in response.headers["content-disposition"]
    assert "circuit_abcdefgh.net" in response.headers["content-disposition"]
    assert "R1 N1 N2 1k" in response.text


def test_download_netlist_invalid_circuit_code(client, monkeypatch):
    from backend.agent.tools.circuit_export import CircuitCodeError

    _SESSION_CONTEXTS["sess-bad"] = {"circuit": "syntax error(("}
    monkeypatch.setattr(
        downloads_router,
        "convert_code_to_netlist",
        lambda code: (_ for _ in ()).throw(CircuitCodeError("bad code")),
    )

    response = client.get("/download/netlist/sess-bad")
    assert response.status_code == 400
    assert "bad code" in response.json()["detail"]


def test_download_project_unknown_session(client):
    response = client.get("/download/project/ghost")
    assert response.status_code == 404


def test_download_project_zips_existing_folder(client, seeded_session, tmp_path):
    extra_dir = tmp_path / "project_copy"
    extra_dir.mkdir()
    (extra_dir / "main.kicad_sch").write_text("(kicad_sch)")

    session_id = seeded_session["session_id"]
    context = dict(seeded_session["context"])
    context["kicad_project_path"] = str(extra_dir)
    _SESSION_CONTEXTS[session_id] = context

    response = client.get(f"/download/project/{session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    archive = zipfile.ZipFile(BytesIO(response.content))
    assert "main.kicad_sch" in archive.namelist()


def test_download_project_regenerates_from_circuit_code(client, tmp_path, monkeypatch):
    session_id = "sess-regen"

    def fake_build(code):
        return object()  # opaque circuit handle

    generated_dir = tmp_path / "regenerated"
    generated_dir.mkdir()
    (generated_dir / "regen.kicad_sch").write_text("(kicad_sch)")

    def fake_generate(circuits, output_dir, project_name):
        return str(generated_dir)

    monkeypatch.setattr(downloads_router, "build_circuit_from_code", fake_build)
    monkeypatch.setattr(downloads_router, "generate_kicad_project", fake_generate)
    _SESSION_CONTEXTS[session_id] = {
        "kicad_project_path": None,
        "kicad_project_name": "regen_project",
        "circuit": "circuit = Circuit()",
    }

    response = client.get(f"/download/project/{session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(BytesIO(response.content))
    assert "regen.kicad_sch" in archive.namelist()


def test_download_project_regeneration_failure(client, monkeypatch):
    session_id = "sess-regen-fail"

    def boom(code):
        raise RuntimeError("cannot parse circuit")

    monkeypatch.setattr(downloads_router, "build_circuit_from_code", boom)
    _SESSION_CONTEXTS[session_id] = {"circuit": "junk"}

    response = client.get(f"/download/project/{session_id}")
    assert response.status_code == 500
    assert "Could not regenerate KiCad project" in response.json()["detail"]


def test_download_project_nothing_available(client):
    _SESSION_CONTEXTS["sess-empty"] = {"unrelated": "value"}
    response = client.get("/download/project/sess-empty")
    assert response.status_code == 404
    assert "No KiCad project is available" in response.json()["detail"]
