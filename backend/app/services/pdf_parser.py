from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


class PDFParseError(ValueError):
    pass


class ScannedPDFError(PDFParseError):
    pass


@dataclass(frozen=True)
class PDFParseResult:
    text: str
    page_count: int


def extract_pdf_text(file_bytes: bytes) -> PDFParseResult:
    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:  # pypdf raises several parser-specific exceptions.
        raise PDFParseError("无法读取 PDF 文件，请确认文件未损坏且未加密。") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PDFParseError("暂不支持需要密码的 PDF 文件。") from exc

    page_texts: list[str] = []
    extracted_char_count = 0
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        text = text.strip()
        extracted_char_count += len(text)
        if text:
            page_texts.append(f"--- Page {index} ---\n{text}")

    text = "\n\n".join(page_texts).strip()
    if extracted_char_count == 0:
        raise ScannedPDFError(
            "该 PDF 没有可复制文本，可能是图片扫描版简历，正在尝试 OCR 识别。"
        )
    return PDFParseResult(text=text, page_count=len(reader.pages))
