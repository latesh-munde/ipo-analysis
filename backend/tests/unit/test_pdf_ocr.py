import subprocess

import pymupdf as fitz
import pytest
from app.services import pdf_ocr
from app.services.pdf_ocr import OcrProcessingError, OcrUnavailableError


def test_tesseract_tsv_is_returned_with_normalized_confidence(monkeypatch) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "OCR")
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\t"
        "width\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t10\t30\t10\t90.50\tRevenue\n"
    )
    monkeypatch.setattr(pdf_ocr.shutil, "which", lambda _executable: "tesseract")

    def tesseract(*args, **kwargs):
        output = "tesseract v5.5.3\n" if args[0][1] == "--version" else tsv
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout=output,
            stderr="",
        )

    monkeypatch.setattr(pdf_ocr.subprocess, "run", tesseract)

    try:
        result = pdf_ocr.recognize_page_with_layout(
            page,
            executable="tesseract",
            language="eng",
            timeout_seconds=10,
            dpi=150,
        )
        text, confidence = pdf_ocr.recognize_page(
            page,
            executable="tesseract",
            language="eng",
            timeout_seconds=10,
            dpi=150,
        )
    finally:
        pdf.close()

    assert text == "Revenue"
    assert confidence == pytest.approx(0.905)
    assert result.text == text
    assert result.words[0].text == "Revenue"
    assert result.words[0].confidence == pytest.approx(90.5)
    assert (result.words[0].x0, result.words[0].y0) == (10, 10)
    assert (result.words[0].x1, result.words[0].y1) == (40, 20)
    assert result.words[0].line_id == (1, 1, 1)
    assert result.engine_version == "5.5.3"


def test_missing_tesseract_is_an_explicit_error(monkeypatch) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    monkeypatch.setattr(pdf_ocr.shutil, "which", lambda _executable: None)

    try:
        with pytest.raises(OcrUnavailableError):
            pdf_ocr.recognize_page(
                page,
                executable="missing-tesseract",
                language="eng",
                timeout_seconds=1,
                dpi=100,
            )
    finally:
        pdf.close()


def test_tesseract_timeout_is_an_explicit_error(monkeypatch) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    monkeypatch.setattr(pdf_ocr.shutil, "which", lambda _executable: "tesseract")

    def timeout(*args, **kwargs):
        if args[0][1] == "--version":
            return subprocess.CompletedProcess(
                args[0],
                0,
                stdout="tesseract 5.5.3\n",
                stderr="",
            )
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(pdf_ocr.subprocess, "run", timeout)

    try:
        with pytest.raises(OcrProcessingError, match="time limit"):
            pdf_ocr.recognize_page(
                page,
                executable="tesseract",
                language="eng",
                timeout_seconds=1,
                dpi=100,
            )
    finally:
        pdf.close()
