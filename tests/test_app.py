import io
import importlib
from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("OUTPUT_FOLDER", str(tmp_path / "outputs"))
    import dsf_ai.config
    importlib.reload(dsf_ai.config)
    import app as app_module
    importlib.reload(app_module)
    app_module.liasse_extractor.delay = 0
    app_module.form_extractor.delay = 0
    return app_module.app.test_client()


def test_health(client):
    assert client.get("/health").get_json()["demo_mode"] is True


def test_liasse_upload_returns_excel(client):
    pdf = (SAMPLES / "synthetic_liasse.pdf").read_bytes()
    resp = client.post("/extract", data={"pdf": (io.BytesIO(pdf), "sample.pdf")}, content_type="multipart/form-data")
    body = resp.get_json()
    assert resp.status_code == 200 and body["success"]
    assert body["sections_extracted"] == 3
    dl = client.get(f"/download/{body['excel_filename']}")
    assert dl.status_code == 200 and dl.data[:2] == b"PK"


def test_liasse_rejects_non_pdf(client):
    resp = client.post("/extract", data={"pdf": (io.BytesIO(b"x"), "a.txt")}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_download_cannot_escape_output_folder(client):
    assert client.get("/download/../app.py").status_code == 404


def test_forms_extract_and_export(client):
    files = [(io.BytesIO((SAMPLES / f"synthetic_form_{i}.jpg").read_bytes()), f"form_{i}.jpg") for i in (1, 2)]
    body = client.post("/forms/extract", data={"file": files}, content_type="multipart/form-data").get_json()
    assert body["count"] == 2 and not body["errors"]
    resp = client.post("/forms/export", json={"results": body["results"]})
    assert resp.status_code == 200 and resp.data[:2] == b"PK"
