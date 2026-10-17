import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf as fitz


class OcrUnavailableError(RuntimeError):
    pass


class OcrProcessingError(RuntimeError):
    pass


def recognize_page(
    page: fitz.Page,
    *,
    executable: str,
    language: str,
    timeout_seconds: int,
    dpi: int,
) -> tuple[str, float | None]:
    command = shutil.which(executable)
    if command is None:
        raise OcrUnavailableError("The configured Tesseract executable was not found.")

    try:
        with tempfile.TemporaryDirectory(prefix="ipo-ocr-") as temp_dir:
            image_path = Path(temp_dir) / "page.png"
            page.get_pixmap(dpi=dpi, alpha=False).save(image_path)
            result = subprocess.run(
                [
                    command,
                    str(image_path),
                    "stdout",
                    "-l",
                    language,
                    "tsv",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                encoding="utf-8",
                errors="replace",
            )
    except subprocess.TimeoutExpired as exc:
        raise OcrProcessingError("OCR exceeded its configured time limit.") from exc
    except Exception as exc:
        raise OcrProcessingError("The page could not be rendered for OCR.") from exc

    if result.returncode:
        raise OcrProcessingError("Tesseract could not process the rendered page.")

    words: list[str] = []
    confidences: list[float] = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        text = (row.get("text") or "").strip()
        if text:
            words.append(text)
            try:
                confidence = float(row.get("conf", "-1"))
            except ValueError:
                continue
            if confidence >= 0:
                confidences.append(confidence)

    confidence = sum(confidences) / len(confidences) / 100 if confidences else None
    return " ".join(words), confidence
