import asyncio

from backend.app.core.config import Settings
from backend.app.models.schemas import ResumeProfile
from backend.app.services import resume_service
from backend.app.services.pdf_parser import PDFParseResult, ScannedPDFError
from backend.app.services.resume_service import ResumeService, _resume_response_from_cache


def test_analyze_bytes_includes_full_text(monkeypatch, tmp_path):
    monkeypatch.setattr(
        resume_service,
        "extract_pdf_text",
        lambda _: PDFParseResult(
            text="张三\n邮箱：zhangsan@example.com\n技能：Python FastAPI",
            page_count=1,
        ),
    )
    service = ResumeService(
        Settings(_env_file=None, cache_dir=tmp_path, ai_api_key=None, deepseek_api_key=None)
    )

    response = asyncio.run(service.analyze_bytes("resume.pdf", b"fake-pdf"))

    assert response.full_text
    assert response.full_text == response.text_preview
    assert response.page_count == 1
    assert "Python" in response.profile.background_info.skills


def test_old_cache_without_full_text_is_supported():
    record = {
        "text": "缓存中的完整文本",
        "response": {
            "resume_id": "demo",
            "filename": "resume.pdf",
            "content_hash": "demo",
            "page_count": 1,
            "text_preview": "旧预览",
            "sections": [],
            "profile": ResumeProfile().model_dump(mode="json"),
            "from_cache": False,
        },
    }

    response = _resume_response_from_cache(record)

    assert response.full_text == "缓存中的完整文本"


def test_scanned_pdf_uses_ocr_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        resume_service,
        "extract_pdf_text",
        lambda _: (_ for _ in ()).throw(ScannedPDFError("扫描版 PDF")),
    )
    monkeypatch.setattr(
        resume_service,
        "extract_pdf_text_with_ocr",
        lambda _, __: PDFParseResult(
            text="李四\n邮箱：lisi@example.com\n技能：Python",
            page_count=1,
        ),
    )
    service = ResumeService(
        Settings(_env_file=None, cache_dir=tmp_path, ai_api_key=None, deepseek_api_key=None)
    )

    response = asyncio.run(service.analyze_bytes("scan.pdf", b"fake-pdf"))

    assert response.page_count == 1
    assert response.profile.basic_info.name == "李四"
    assert "Python" in response.profile.background_info.skills
