"""DSF Document AI — Flask web app.

Two tools:
  /        Liasse fiscale: upload a multi-page PDF → 3-sheet Excel per company
  /forms   Handwritten DSF forms: upload many scans → one ERETES-format Excel

Run `DEMO_MODE=true python app.py` to try the UI with synthetic data and no
Google Cloud credentials.
"""
import json
import logging
import os
import secrets
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from dsf_ai.config import settings
from dsf_ai.form_excel import export_eretes
from dsf_ai.liasse_excel import build_excel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("dsf_ai.app")

app = Flask(__name__)
app.secret_key = settings.flask_secret_key or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length

UPLOADS = Path(settings.upload_folder)
OUTPUTS = Path(settings.output_folder)
UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

FORM_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def _build_extractors():
    if settings.demo_mode:
        from dsf_ai.demo import DemoFormExtractor, DemoLiasseExtractor

        logger.warning("DEMO_MODE is on — serving synthetic results, no Gemini calls")
        return DemoLiasseExtractor(), DemoFormExtractor()

    from dsf_ai.form import FormExtractor
    from dsf_ai.gemini import GeminiClient
    from dsf_ai.liasse import LiasseExtractor

    client = GeminiClient(settings)
    return (
        LiasseExtractor(client, dpi=settings.pdf_dpi),
        FormExtractor(client, project_id=settings.gcp_project_id, docai_location=settings.docai_location,
                      docai_processor_id=settings.docai_processor_id),
    )


liasse_extractor, form_extractor = _build_extractors()


def _safe_stem(text: str, limit: int = 40) -> str:
    return secure_filename(text or "extraction")[:limit] or "extraction"


# ── Liasse fiscale ─────────────────────────────────────────────────
@app.route("/")
def index():
    history = []
    for f in sorted(OUTPUTS.glob("DSF_*.xlsx"), key=os.path.getmtime, reverse=True)[:10]:
        meta_path = f.with_suffix(".json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        history.append({
            "filename": f.name,
            "company": meta.get("company", f.stem),
            "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
            "pages": meta.get("total_pages", "?"),
        })
    return render_template("liasse.html", history=history, demo=settings.demo_mode, active="liasse")


@app.route("/extract", methods=["POST"])
def extract_liasse():
    pdf = request.files.get("pdf")
    if not pdf or not pdf.filename:
        return jsonify({"error": "Aucun fichier PDF envoyé"}), 400
    if not pdf.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Le fichier doit être un PDF"}), 400

    job_id = uuid.uuid4().hex[:8]
    pdf_path = UPLOADS / f"{job_id}_{secure_filename(pdf.filename)}"
    pdf.save(pdf_path)
    try:
        data = liasse_extractor.extract_pdf(str(pdf_path))
        ident = data.get("identification", {})
        company, nif = ident.get("nom_entreprise", "extraction"), ident.get("nif", "")
        excel_name = f"DSF_{_safe_stem(company)}_{job_id}.xlsx"
        build_excel(data, str(OUTPUTS / excel_name))

        sections = sum(1 for k in ("identification", "bilan", "compte_resultat") if data.get(k))
        meta = {"company": company, "nif": nif, "total_pages": data.get("total_pages", 0),
                "sections_extracted": sections, "page_classification": data.get("page_classification", {})}
        (OUTPUTS / excel_name).with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False))
        (OUTPUTS / f"raw_{job_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return jsonify({"success": True, "excel_filename": excel_name, **meta,
                        "pages_skipped_early": data.get("pages_skipped_early", 0)})
    except Exception as exc:
        logger.exception("Extraction failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        pdf_path.unlink(missing_ok=True)


@app.route("/download/<path:filename>")
def download(filename):
    if not filename.endswith(".xlsx"):
        abort(404)
    return send_from_directory(OUTPUTS.resolve(), filename, as_attachment=True)


# ── Handwritten forms ──────────────────────────────────────────────
@app.route("/forms")
def forms():
    return render_template("forms.html", demo=settings.demo_mode, active="forms")


@app.route("/forms/extract", methods=["POST"])
def extract_forms():
    files = [f for f in request.files.getlist("file") if f and f.filename]
    if not files:
        return jsonify({"success": False, "error": "Aucun fichier"}), 400

    results, errors = [], []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in FORM_EXTENSIONS:
            errors.append({"file": f.filename, "error": "Type non supporté"})
            continue
        path = UPLOADS / secure_filename(f"{uuid.uuid4().hex[:8]}_{f.filename}")
        f.save(path)
        image_path = path
        try:
            if ext == ".pdf":  # forms are single-page: use the first page
                from dsf_ai.imaging import pdf_to_images

                image_path = path.with_suffix(".jpg")
                pdf_to_images(str(path), dpi=300, first_page=1, last_page=1)[0].save(image_path, "JPEG", quality=95)
            data = form_extractor.extract(str(image_path))
            data["_source_file"] = f.filename
            results.append(data)
        except Exception as exc:
            logger.exception("Form extraction failed: %s", f.filename)
            errors.append({"file": f.filename, "error": str(exc)})
        finally:
            path.unlink(missing_ok=True)
            Path(image_path).unlink(missing_ok=True)

    return jsonify({"success": bool(results), "results": results, "errors": errors, "count": len(results)})


@app.route("/forms/export", methods=["POST"])
def export_forms():
    payload = request.get_json(silent=True) or {}
    if not payload.get("results"):
        return jsonify({"success": False, "error": "Rien à exporter"}), 400
    name = f"DSF_ERETES_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    path = OUTPUTS / name
    export_eretes(payload["results"], str(path))
    return send_file(path.resolve(), as_attachment=True, download_name=name)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "demo_mode": settings.demo_mode, "model": settings.gemini_model})


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("DEBUG", "false").lower() == "true")
