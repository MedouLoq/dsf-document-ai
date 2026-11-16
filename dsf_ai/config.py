"""Runtime configuration, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Gemini — either Vertex AI (service account / ADC) or a Gemini API key
    gcp_project_id: str = field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", ""))
    gcp_location: str = field(default_factory=lambda: os.getenv("GCP_LOCATION", "us-central1"))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    gemini_timeout_sec: int = field(default_factory=lambda: int(os.getenv("GEMINI_TIMEOUT_SEC", "90")))
    gemini_call_delay_sec: float = field(default_factory=lambda: float(os.getenv("GEMINI_CALL_DELAY_SEC", "1.5")))

    # Optional Document AI Form Parser (handwritten-form pipeline)
    docai_processor_id: str = field(default_factory=lambda: os.getenv("DOCAI_PROCESSOR_ID", ""))
    docai_location: str = field(default_factory=lambda: os.getenv("DOCAI_LOCATION", "us"))

    # Web app
    flask_secret_key: str = field(default_factory=lambda: os.getenv("FLASK_SECRET_KEY", ""))
    upload_folder: str = field(default_factory=lambda: os.getenv("UPLOAD_FOLDER", "uploads"))
    output_folder: str = field(default_factory=lambda: os.getenv("OUTPUT_FOLDER", "outputs"))
    max_content_length: int = field(default_factory=lambda: int(os.getenv("MAX_CONTENT_LENGTH", str(100 * 1024 * 1024))))
    pdf_dpi: int = field(default_factory=lambda: int(os.getenv("PDF_DPI", "200")))

    # Demo mode: serve synthetic results, no Google Cloud calls
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE"))


settings = Settings()
