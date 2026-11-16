"""Crash-safe batch extraction of liasse-fiscale PDFs.

Source can be a local folder or any rclone remote (e.g. Google Drive):

    python batch.py --source ./pdfs
    python batch.py --source gdrive:"DSF 2024" --batch-size 10
    python batch.py --source gdrive:"DSF 2024" --dry-run

Progress is checkpointed to <output>/progress.json after every file, so an
interrupted run resumes where it stopped. Watch it live with dashboard.py.
"""
import argparse
import json
import logging
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from dsf_ai.config import settings
from dsf_ai.imaging import drop_blank_pages, pdf_to_images
from dsf_ai.liasse_excel import build_excel

logger = logging.getLogger("dsf_ai.batch")
MIN_FREE_GB = 2.0


class Source:
    """A folder of PDFs: local path or rclone remote ('remote:path')."""

    def __init__(self, spec: str):
        self.spec = spec
        self.remote = ":" in spec and not Path(spec).exists()

    def list_pdfs(self) -> list:
        if not self.remote:
            return sorted(p.name for p in Path(self.spec).iterdir() if p.suffix.lower() == ".pdf")
        out = subprocess.run(["rclone", "lsjson", self.spec, "--include", "*.{pdf,PDF}"],
                             capture_output=True, text=True, check=True).stdout
        return sorted(f["Name"] for f in json.loads(out) if not f.get("IsDir"))

    def fetch(self, name: str, dest: Path) -> Path:
        if not self.remote:
            return Path(self.spec) / name
        subprocess.run(["rclone", "copy", f"{self.spec}/{name}", str(dest)], capture_output=True, text=True, check=True)
        return dest / name


class BatchProcessor:
    def __init__(self, source: Source, output_dir: Path, extractor, batch_size: int = 10, dpi: int = 200):
        self.source, self.out, self.extractor = source, output_dir, extractor
        self.batch_size, self.dpi = batch_size, dpi
        self.out.mkdir(parents=True, exist_ok=True)
        self.progress_file, self.errors_file = self.out / "progress.json", self.out / "errors.json"
        self.progress = self._load(self.progress_file, {
            "started_at": datetime.now().isoformat(), "completed_files": [], "skipped_files": [],
            "failed_files": [], "total_found": 0, "total_completed": 0, "total_failed": 0,
        })
        self.errors = self._load(self.errors_file, [])

    @staticmethod
    def _load(path: Path, default):
        return json.loads(path.read_text()) if path.exists() else default

    def _save(self):
        p = self.progress
        p["last_updated"] = datetime.now().isoformat()
        p["total_completed"], p["total_failed"] = len(p["completed_files"]), len(p["failed_files"])
        self.progress_file.write_text(json.dumps(p, ensure_ascii=False, indent=2))
        self.errors_file.write_text(json.dumps(self.errors, ensure_ascii=False, indent=2))

    def done(self, name: str) -> bool:
        return name in self.progress["completed_files"] or name in self.progress["skipped_files"]

    def process_single(self, pdf_path: Path, name: str) -> dict:
        result = {"filename": name}
        try:
            images = pdf_to_images(str(pdf_path), dpi=self.dpi)   # rasterise once
            total = len(images)
            images = drop_blank_pages(images)
        except Exception as exc:
            return {**result, "status": "conversion_failed", "error": str(exc)}
        if not images:
            return {**result, "status": "skipped_blank"}

        try:
            data = self.extractor.extract_images(images, source_name=name)
        except Exception as exc:
            return {**result, "status": "extraction_failed", "error": str(exc)}
        finally:
            del images

        ident = data.get("identification", {})
        company, nif = ident.get("nom_entreprise", ""), ident.get("nif", "")
        if not (company or nif or data.get("bilan") or data.get("compte_resultat")):
            return {**result, "status": "skipped_not_dsf", "page_classification": data.get("page_classification", {})}

        stem = f"DSF_{(company or 'unknown').replace(' ', '_').replace('/', '-')[:40]}_{(nif or 'no_nif').replace('/', '-')}"
        excel_path, n = self.out / f"{stem}.xlsx", 1
        while excel_path.exists():
            excel_path, n = self.out / f"{stem}_{n}.xlsx", n + 1
        try:
            build_excel(data, str(excel_path))
        except Exception as exc:
            return {**result, "status": "excel_failed", "error": str(exc)}
        excel_path.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return {**result, "status": "success", "excel_file": excel_path.name, "pages_total": total,
                "sections_extracted": sum(1 for k in ("identification", "bilan", "compte_resultat") if data.get(k))}

    def run(self):
        files = self.source.list_pdfs()
        self.progress["total_found"] = len(files)
        self._save()
        remaining = [f for f in files if not self.done(f)]
        logger.info("PDFs: %d total, %d already done, %d remaining", len(files), len(files) - len(remaining), len(remaining))

        with tempfile.TemporaryDirectory(prefix="dsf_batch_") as tmp:
            tmp = Path(tmp)
            for start in range(0, len(remaining), self.batch_size):
                batch = remaining[start:start + self.batch_size]
                logger.info("── Batch %d/%d ──", start // self.batch_size + 1, -(-len(remaining) // self.batch_size))
                for name in batch:
                    try:
                        res = self.process_single(self.source.fetch(name, tmp), name)
                    except Exception as exc:
                        res = {"filename": name, "status": "fatal", "error": str(exc)}
                    status = res["status"]
                    if status == "success":
                        self.progress["completed_files"].append(name)
                    elif status.startswith("skipped"):
                        self.progress["skipped_files"].append(name)
                    else:
                        self.progress["failed_files"].append(name)
                        self.errors.append(res)
                    logger.info("%s → %s", name, status)
                    if self.source.remote:
                        for f in tmp.glob("*"):
                            f.unlink(missing_ok=True)
                    self._save()
                    time.sleep(1)
                if shutil.disk_usage(self.out).free / 1024 ** 3 < MIN_FREE_GB:
                    logger.warning("Low disk space — pausing. Re-run the same command to resume.")
                    break

        p = self.progress
        logger.info("Finished: %d ok, %d skipped, %d failed of %d", len(p["completed_files"]),
                    len(p["skipped_files"]), len(p["failed_files"]), p["total_found"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="local folder or rclone remote, e.g. gdrive:DSF")
    ap.add_argument("--output", default="batch_outputs", help="output folder (default: batch_outputs)")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--dpi", type=int, default=settings.pdf_dpi)
    ap.add_argument("--dry-run", action="store_true", help="list what would be processed and exit")
    args = ap.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(out / "batch.log")])

    source = Source(args.source)
    if args.dry_run:
        files = source.list_pdfs()
        print(f"{len(files)} PDFs found in {args.source}")
        for f in files[:20]:
            print("  ", f)
        return

    from dsf_ai.gemini import GeminiClient
    from dsf_ai.liasse import LiasseExtractor

    extractor = LiasseExtractor(GeminiClient(settings), dpi=args.dpi)
    BatchProcessor(source, out, extractor, batch_size=args.batch_size, dpi=args.dpi).run()


if __name__ == "__main__":
    main()
