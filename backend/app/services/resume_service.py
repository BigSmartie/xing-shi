from __future__ import annotations

import hashlib

from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import Settings
from backend.app.models.schemas import AnalyzeAndMatchResponse, MatchScoreResponse, ResumeAnalysisResponse
from backend.app.services.cache import JsonFileCache
from backend.app.services.extractor import ResumeExtractor
from backend.app.services.matcher import ResumeMatcher, build_match_cache_key
from backend.app.services.ocr_service import OCRUnavailableError, extract_pdf_text_with_ocr
from backend.app.services.pdf_parser import PDFParseError, ScannedPDFError, extract_pdf_text
from backend.app.services.text_cleaner import clean_text, split_sections


RESUME_CACHE_VERSION = "resume-v8-ai-first-extraction"
MATCH_CACHE_VERSION = "match-v7-ai-first-scoring"


class ResumeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = JsonFileCache(settings.cache_dir)
        self.extractor = ResumeExtractor(settings)
        self.matcher = ResumeMatcher(settings)

    async def analyze_upload(
        self,
        upload: UploadFile,
        force_refresh: bool = False,
    ) -> ResumeAnalysisResponse:
        filename = upload.filename or "resume.pdf"
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅支持上传 PDF 格式的简历文件。",
            )
        file_bytes = await upload.read()
        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大支持 {self.settings.max_upload_mb}MB。",
            )
        if not file_bytes:
            raise HTTPException(status_code=400, detail="上传文件为空。")
        return await self.analyze_bytes(filename, file_bytes, force_refresh)

    async def analyze_and_match_upload(
        self,
        upload: UploadFile,
        job_description: str | None,
        force_refresh: bool = False,
    ) -> AnalyzeAndMatchResponse:
        filename, file_bytes = await self._read_upload(upload)
        if not job_description or not job_description.strip():
            resume = await self.analyze_bytes(filename, file_bytes, force_refresh)
            return AnalyzeAndMatchResponse(resume=resume, match=None)

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        cache_key = build_match_cache_key(content_hash, job_description)
        cached_resume = self.cache.get("resume", content_hash)
        cached_match = self.cache.get("match", cache_key)
        if (
            cached_resume
            and cached_resume.get("version") == RESUME_CACHE_VERSION
            and cached_match
            and cached_match.get("version") == MATCH_CACHE_VERSION
            and not force_refresh
        ):
            resume = _resume_response_from_cache(cached_resume)
            match = MatchScoreResponse.model_validate(cached_match["response"])
            return AnalyzeAndMatchResponse(
                resume=resume.model_copy(update={"from_cache": True}),
                match=match.model_copy(update={"from_cache": True}),
            )

        if cached_resume and cached_resume.get("version") == RESUME_CACHE_VERSION and not force_refresh:
            resume = _resume_response_from_cache(cached_resume)
            cleaned_text = str(cached_resume.get("text") or resume.full_text or resume.text_preview)
            match = await self.matcher.match(
                resume_id=resume.resume_id,
                profile=resume.profile,
                resume_text=cleaned_text,
                job_description=job_description,
            )
            self._cache_match(cache_key, match)
            return AnalyzeAndMatchResponse(
                resume=resume.model_copy(update={"from_cache": True}),
                match=match,
            )

        parsed = self._parse_pdf_bytes(file_bytes)
        cleaned_text = clean_text(parsed.text)
        heuristic_profile = self.extractor._heuristic_extract(cleaned_text)
        ai_bundle = await self.extractor.ai_client.analyze_resume_and_match(
            cleaned_text,
            job_description,
        )
        if ai_bundle:
            ai_resume = ai_bundle.get("resume") if isinstance(ai_bundle.get("resume"), dict) else {}
            profile = self.extractor._merge_ai_data(heuristic_profile, ai_resume, cleaned_text)
        else:
            profile = heuristic_profile

        resume = self._build_resume_response(
            content_hash=content_hash,
            filename=filename,
            page_count=parsed.page_count,
            cleaned_text=cleaned_text,
            profile=profile,
        )
        self._cache_resume(content_hash, resume, cleaned_text)

        ai_match = ai_bundle.get("match") if ai_bundle and isinstance(ai_bundle.get("match"), dict) else None
        match = await self.matcher.match(
            resume_id=resume.resume_id,
            profile=resume.profile,
            resume_text=cleaned_text,
            job_description=job_description,
            ai_result=ai_match if ai_bundle else {},
        )
        self._cache_match(cache_key, match)
        return AnalyzeAndMatchResponse(resume=resume, match=match)

    async def analyze_bytes(
        self,
        filename: str,
        file_bytes: bytes,
        force_refresh: bool = False,
    ) -> ResumeAnalysisResponse:
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        cached = self.cache.get("resume", content_hash)
        if cached and cached.get("version") == RESUME_CACHE_VERSION and not force_refresh:
            response = _resume_response_from_cache(cached)
            return response.model_copy(update={"from_cache": True})

        parsed = self._parse_pdf_bytes(file_bytes)

        cleaned_text = clean_text(parsed.text)
        profile = await self.extractor.extract(cleaned_text)
        response = self._build_resume_response(
            content_hash=content_hash,
            filename=filename,
            page_count=parsed.page_count,
            cleaned_text=cleaned_text,
            profile=profile,
        )
        self._cache_resume(content_hash, response, cleaned_text)
        return response

    def _build_resume_response(
        self,
        content_hash: str,
        filename: str,
        page_count: int,
        cleaned_text: str,
        profile,
    ) -> ResumeAnalysisResponse:
        return ResumeAnalysisResponse(
            resume_id=content_hash,
            filename=filename,
            content_hash=content_hash,
            page_count=page_count,
            full_text=cleaned_text,
            text_preview=cleaned_text[:12000],
            sections=split_sections(cleaned_text),
            profile=profile,
            from_cache=False,
        )

    def _cache_resume(
        self,
        content_hash: str,
        response: ResumeAnalysisResponse,
        cleaned_text: str,
    ) -> None:
        self.cache.set(
            "resume",
            content_hash,
            {
                "version": RESUME_CACHE_VERSION,
                "response": response.model_dump(mode="json"),
                "text": cleaned_text,
            },
        )

    def _cache_match(self, cache_key: str, response: MatchScoreResponse) -> None:
        self.cache.set(
            "match",
            cache_key,
            {
                "version": MATCH_CACHE_VERSION,
                "response": response.model_dump(mode="json"),
            },
        )

    async def _read_upload(self, upload: UploadFile) -> tuple[str, bytes]:
        filename = upload.filename or "resume.pdf"
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仅支持上传 PDF 格式的简历文件。",
            )
        file_bytes = await upload.read()
        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大，最大支持 {self.settings.max_upload_mb}MB。",
            )
        if not file_bytes:
            raise HTTPException(status_code=400, detail="上传文件为空。")
        return filename, file_bytes

    def _parse_pdf_bytes(self, file_bytes: bytes):
        try:
            return extract_pdf_text(file_bytes)
        except ScannedPDFError as exc:
            try:
                return extract_pdf_text_with_ocr(file_bytes, self.settings)
            except OCRUnavailableError as ocr_exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"{exc} {ocr_exc}",
                ) from ocr_exc
        except PDFParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def match_resume(
        self,
        resume_id: str,
        job_description: str,
        force_refresh: bool = False,
    ) -> MatchScoreResponse:
        record = self.cache.get("resume", resume_id)
        if not record:
            raise HTTPException(status_code=404, detail="未找到该简历，请先上传解析。")

        cache_key = build_match_cache_key(resume_id, job_description)
        cached = self.cache.get("match", cache_key)
        if cached and cached.get("version") == MATCH_CACHE_VERSION and not force_refresh:
            response = MatchScoreResponse.model_validate(cached["response"])
            return response.model_copy(update={"from_cache": True})

        resume = _resume_response_from_cache(record)
        text = str(record.get("text") or resume.text_preview)
        response = await self.matcher.match(
            resume_id=resume_id,
            profile=resume.profile,
            resume_text=text,
            job_description=job_description,
        )
        self._cache_match(cache_key, response)
        return response


def _resume_response_from_cache(record: dict) -> ResumeAnalysisResponse:
    response_data = dict(record["response"])
    cached_text = str(record.get("text") or response_data.get("text_preview") or "")
    response_data.setdefault("full_text", cached_text)
    response_data.setdefault("text_preview", cached_text[:12000])
    return ResumeAnalysisResponse.model_validate(response_data)
