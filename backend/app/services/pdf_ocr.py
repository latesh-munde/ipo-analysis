import csv
import io
import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pymupdf as fitz


class OcrUnavailableError(RuntimeError):
    pass


class OcrProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float | None
    x0: float
    y0: float
    x1: float
    y1: float
    line_id: tuple[int, int, int]


@dataclass(frozen=True)
class OcrPageResult:
    text: str
    confidence: float | None
    words: list[OcrWord]
    engine_version: str | None = None


def recognize_page(
    page: fitz.Page,
    *,
    executable: str,
    language: str,
    timeout_seconds: float,
    dpi: int,
) -> tuple[str, float | None]:
    result = recognize_page_with_layout(
        page,
        executable=executable,
        language=language,
        timeout_seconds=timeout_seconds,
        dpi=dpi,
    )
    return result.text, result.confidence


def recognize_page_with_layout(
    page: fitz.Page,
    *,
    executable: str,
    language: str,
    timeout_seconds: float,
    dpi: int,
) -> OcrPageResult:
    command = shutil.which(executable)
    if Path(executable).is_file():
        command = str(Path(executable).resolve())
    if command is None:
        raise OcrUnavailableError("The configured Tesseract executable was not found.")
    engine_version = _get_tesseract_version(command)

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

    words: list[OcrWord] = []
    confidences: list[float] = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        text = (row.get("text") or "").strip()
        if text:
            try:
                confidence = float(row.get("conf", "-1"))
            except ValueError:
                confidence = -1
            if confidence >= 0:
                confidences.append(confidence)
            try:
                x0 = float(row["left"])
                y0 = float(row["top"])
                width = float(row["width"])
                height = float(row["height"])
                line_id = (
                    int(row["block_num"]),
                    int(row["par_num"]),
                    int(row["line_num"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise OcrProcessingError(
                    "Tesseract returned invalid word geometry."
                ) from exc
            if (
                not all(math.isfinite(value) for value in (x0, y0, width, height))
                or min(x0, y0) < 0
                or min(width, height) <= 0
            ):
                raise OcrProcessingError("Tesseract returned invalid word geometry.")
            words.append(
                OcrWord(
                    text=text,
                    confidence=confidence if confidence >= 0 else None,
                    x0=x0,
                    y0=y0,
                    x1=x0 + width,
                    y1=y0 + height,
                    line_id=line_id,
                )
            )

    confidence = sum(confidences) / len(confidences) / 100 if confidences else None
    text = " ".join(word.text for word in words)
    return OcrPageResult(
        text=text,
        confidence=confidence,
        words=words,
        engine_version=engine_version,
    )


@lru_cache(maxsize=8)
def _get_tesseract_version(command: str) -> str:
    try:
        result = subprocess.run(
            [command, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OcrProcessingError(
            "The Tesseract version could not be determined."
        ) from exc
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    match = re.search(r"tesseract\s+v?([^\s]+)", first_line, re.IGNORECASE)
    if result.returncode != 0 or match is None:
        raise OcrProcessingError("The Tesseract version could not be determined.")
    return match.group(1)
