from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import Settings
from backend.app.services.pdf_parser import PDFParseResult


class OCRUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class OCRPageResult:
    page_number: int
    text: str


def extract_pdf_text_with_ocr(file_bytes: bytes, settings: Settings) -> PDFParseResult:
    if not settings.enable_ocr or settings.ocr_provider == "none":
        raise OCRUnavailableError("当前未启用 OCR，无法解析图片扫描版 PDF。")

    fitz = _import_pymupdf()
    engine = _load_rapidocr_engine()

    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise OCRUnavailableError("OCR 渲染 PDF 失败，请确认文件未损坏。") from exc

    page_results: list[OCRPageResult] = []
    page_limit = min(len(document), settings.ocr_max_pages)
    zoom = settings.ocr_render_dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    for page_index in range(page_limit):
        page = document.load_page(page_index)
        page_texts = []
        for image_bytes in _render_page_ocr_images(fitz, page, matrix):
            page_text = _recognize_image(engine, image_bytes)
            if page_text.strip():
                page_texts.append(page_text.strip())
        page_text = _merge_ocr_texts(page_texts)
        if page_text.strip():
            page_results.append(
                OCRPageResult(page_number=page_index + 1, text=page_text.strip())
            )

    text = "\n\n".join(
        f"--- Page {item.page_number} OCR ---\n{item.text}" for item in page_results
    ).strip()
    if not text:
        raise OCRUnavailableError(
            "OCR 未能识别出有效文字。请尝试上传清晰度更高的 PDF，或先转换为可检索 PDF。"
        )
    return PDFParseResult(text=text, page_count=len(document))


def _import_pymupdf() -> Any:
    try:
        return importlib.import_module("fitz")
    except ModuleNotFoundError as exc:
        raise OCRUnavailableError(
            "缺少 OCR 渲染依赖 PyMuPDF。请运行：pip install -r backend/requirements.txt"
        ) from exc


def _load_rapidocr_engine() -> Any:
    for module_name in ("rapidocr_onnxruntime", "rapidocr"):
        try:
            module = importlib.import_module(module_name)
            return module.RapidOCR()
        except ModuleNotFoundError:
            continue
    raise OCRUnavailableError(
        "缺少 OCR 识别依赖 RapidOCR。请运行：pip install -r backend/requirements.txt"
    )


def _render_page_ocr_images(fitz: Any, page: Any, matrix: Any) -> list[bytes]:
    rect = page.rect
    top_clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + rect.height * 0.28)
    clips = [top_clip, None]
    images: list[bytes] = []
    for clip in clips:
        pixmap = page.get_pixmap(matrix=matrix, clip=clip, alpha=False)
        images.append(pixmap.tobytes("png"))
    return images


def _merge_ocr_texts(texts: list[str]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for line in text.splitlines():
            normalized = " ".join(line.strip().split())
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(line.strip())
    return "\n".join(lines)


def _recognize_image(engine: Any, image_bytes: bytes) -> str:
    try:
        result = engine(image_bytes)
    except Exception as exc:
        raise OCRUnavailableError("OCR 识别过程失败，请稍后重试或更换 PDF。") from exc

    texts = _extract_texts_from_rapidocr_result(result)
    return "\n".join(text for text in texts if text.strip())


def _extract_texts_from_rapidocr_result(result: Any) -> list[str]:
    if result is None:
        return []

    for attr in ("txts", "rec_texts"):
        value = getattr(result, attr, None)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]

    if isinstance(result, dict):
        for key in ("txts", "rec_texts", "texts"):
            value = result.get(key)
            if isinstance(value, list):
                return [str(item) for item in value if str(item).strip()]

    if isinstance(result, tuple) and result:
        return _extract_texts_from_rapidocr_result(result[0])

    if isinstance(result, list):
        texts: list[str] = []
        for item in result:
            if isinstance(item, dict):
                text = item.get("text") or item.get("rec_text")
                if text:
                    texts.append(str(text))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                text = item[1]
                if isinstance(text, str):
                    texts.append(text)
        return texts

    return []
