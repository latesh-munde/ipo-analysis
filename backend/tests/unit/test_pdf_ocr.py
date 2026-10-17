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
    monkeypatch.setattr(
        pdf_ocr.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            stdout=tsv,
            stderr="",
        ),
    )

    try:
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
