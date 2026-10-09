"""Download official Vietnamese/English Tesseract models into project data/tools."""

import hashlib
import json
from pathlib import Path

import requests

root = Path(__file__).resolve().parents[1] / "data" / "tools" / "tessdata"
root.mkdir(parents=True, exist_ok=True)
models = []
for language in ("vie", "eng"):
    url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/{language}.traineddata"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    target = root / f"{language}.traineddata"
    target.write_bytes(response.content)
    models.append({"language": language, "url": url, "sha256": hashlib.sha256(response.content).hexdigest()})
(root / "models.json").write_text(json.dumps(models, indent=2), encoding="utf-8")
print("Downloaded official vie+eng models:", root)
