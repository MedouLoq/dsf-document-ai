"""Demo mode: canned synthetic results instead of Gemini calls.

Lets the web app run end-to-end (upload → JSON → Excel) without any
Google Cloud credentials. All data comes from samples/ and is fictional.
"""
import copy
import itertools
import json
import os
import time
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class DemoLiasseExtractor:
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._data = json.loads((SAMPLES / "synthetic_liasse.json").read_text())

    def extract_pdf(self, pdf_path: str) -> dict:
        time.sleep(self.delay)
        data = copy.deepcopy(self._data)
        data["source_file"] = os.path.basename(pdf_path)
        return data


class DemoFormExtractor:
    def __init__(self, delay: float = 0.6):
        self.delay = delay
        self._cycle = itertools.cycle(json.loads((SAMPLES / "synthetic_forms.json").read_text()))

    def extract(self, image_path: str) -> dict:
        time.sleep(self.delay)
        data = copy.deepcopy(next(self._cycle))
        data["_source_file"] = os.path.basename(image_path)
        return data
