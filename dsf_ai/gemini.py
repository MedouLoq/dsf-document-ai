"""Thin wrapper around the Google Gen AI SDK: retries, rate-limit backoff, JSON parsing."""
import json
import logging
import re
import time
from typing import Iterable, Tuple

from .config import Settings

logger = logging.getLogger(__name__)

ImagePart = Tuple[bytes, str]  # (data, mime_type)


class GeminiClient:
    """Sends images + a prompt to Gemini and returns the text response.

    Uses Vertex AI when GCP_PROJECT_ID is set (credentials from
    GOOGLE_APPLICATION_CREDENTIALS / ADC), otherwise a Gemini API key.
    """

    def __init__(self, settings: Settings):
        from google import genai
        from google.genai import types

        self._types = types
        self.model = settings.gemini_model
        self.call_delay = settings.gemini_call_delay_sec
        http_options = types.HttpOptions(timeout=settings.gemini_timeout_sec * 1000)

        if settings.gcp_project_id:
            self._client = genai.Client(vertexai=True, project=settings.gcp_project_id,
                                        location=settings.gcp_location, http_options=http_options)
            backend = f"Vertex AI ({settings.gcp_project_id}/{settings.gcp_location})"
        elif settings.gemini_api_key:
            self._client = genai.Client(api_key=settings.gemini_api_key, http_options=http_options)
            backend = "Gemini API"
        else:
            raise RuntimeError(
                "No Gemini credentials configured. Set GCP_PROJECT_ID (+ GOOGLE_APPLICATION_CREDENTIALS) "
                "or GEMINI_API_KEY, or run with DEMO_MODE=true."
            )
        logger.info("Gemini client ready: model=%s via %s", self.model, backend)

    def generate(self, images: Iterable[ImagePart], prompt: str, *, temperature: float = 0.0,
                 max_tokens: int = 8192, retries: int = 4) -> str:
        types = self._types
        parts = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]
        parts.append(types.Part.from_text(text=prompt))
        config = types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens)

        time.sleep(self.call_delay)  # stay under per-minute quotas on long batches
        for attempt in range(retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=[types.Content(role="user", parts=parts)],
                    config=config,
                )
                return response.text or ""
            except Exception as exc:  # network errors, 429s, timeouts
                msg = str(exc)
                logger.warning("Gemini attempt %d failed: %s", attempt + 1, msg[:150])
                if attempt == retries:
                    raise
                if "429" in msg or "exhausted" in msg.lower():
                    wait = 10 * (2 ** attempt)
                    logger.warning("Rate limited, waiting %ds", wait)
                elif "timeout" in msg.lower() or "deadline" in msg.lower():
                    wait = 15 * (attempt + 1)
                else:
                    wait = 2 * (attempt + 1)
                time.sleep(wait)
        return ""


def parse_json_response(text: str) -> dict:
    """Parse a model response that should be a JSON object.

    Tolerates markdown fences, leading/trailing prose and trailing commas.
    """
    if not text:
        raise ValueError("Empty model response")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in response: {text[:200]!r}")
    cleaned = cleaned[start:end + 1]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse error: %s — raw: %s", exc, text[:400])
        raise ValueError(f"Failed to parse JSON: {exc}") from exc
