from __future__ import annotations

import hashlib
import re

from backend.app.core.config import Settings
from backend.app.models.schemas import MatchDimensionScores, MatchScoreResponse, ResumeProfile
from backend.app.services.ai_client import AIClient
from backend.app.services.extractor import SKILL_ALIASES, _alias_present, extract_skills


DEGREE_ORDER = {
    "大专": 1,
    "专科": 1,
    "本科": 2,
    "学士": 2,
    "研究生": 3,
    "硕士": 3,
    "博士": 4,
}


class ResumeMatcher:
    def __init__(self, settings: Settings) -> None:
        self.ai_client = AIClient(settings)

    async def match(
        self,
        resume_id: str,
        profile: ResumeProfile,
        resume_text: str,
        job_description: str,
        ai_result: dict | None = None,
    ) -> MatchScoreResponse:
        resume_keywords = _unique(extract_skills(resume_text) + profile.background_info.skills)
        job_keywords = _extract_job_keywords(job_description)
        matched = [kw for kw in job_keywords if _keyword_in_resume(kw, resume_keywords, resume_text)]
        missing = [kw for kw in job_keywords if kw not in matched]

        skill_score = _ratio_score(len(matched), len(job_keywords), default=70.0)
        experience_score = _experience_score(profile, job_description)
        education_score = _education_score(profile, job_description)
        coverage_score = _coverage_score(resume_text, job_description)

        rule_score = (
            skill_score * 0.55
            + experience_score * 0.2
            + education_score * 0.1
            + coverage_score * 0.15
        )

        explanation = _build_explanation(matched, missing, experience_score)
        final_score = round(rule_score, 1)
        recommendation = _recommendation(final_score)

        if ai_result is None:
            ai_result = await self.ai_client.score_match(resume_text, profile, job_description)
        if ai_result:
            ai_score = _coerce_score(ai_result.get("score"))
            if ai_score is not None:
                final_score = round(ai_score, 1)
            ai_dimensions = _ai_dimension_scores(ai_result.get("dimension_scores"))
            if ai_dimensions:
                skill_score = ai_dimensions.skill_match
                experience_score = ai_dimensions.experience_relevance
                education_score = ai_dimensions.education_fit
                coverage_score = ai_dimensions.keyword_coverage
            matched = _list_of_strings(ai_result.get("matched_keywords")) or matched
            missing = _list_of_strings(ai_result.get("missing_keywords")) or missing
            resume_keywords = _list_of_strings(ai_result.get("resume_keywords")) or resume_keywords
            job_keywords = _list_of_strings(ai_result.get("job_keywords")) or job_keywords
            recommendation = str(ai_result.get("recommendation") or _recommendation(final_score))[:80]
            explanation = str(ai_result.get("explanation") or explanation)[:160]

        return MatchScoreResponse(
            resume_id=resume_id,
            score=final_score,
            dimension_scores=MatchDimensionScores(
                skill_match=round(skill_score, 1),
                experience_relevance=round(experience_score, 1),
                education_fit=round(education_score, 1),
                keyword_coverage=round(coverage_score, 1),
            ),
            matched_keywords=matched[:30],
            missing_keywords=missing[:30],
            resume_keywords=resume_keywords[:40],
            job_keywords=job_keywords[:40],
            recommendation=recommendation,
            explanation=explanation,
        )


def build_match_cache_key(resume_id: str, job_description: str) -> str:
    raw = f"{resume_id}\n{job_description.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _extract_job_keywords(job_description: str) -> list[str]:
    skill_keywords = extract_skills(job_description)
    for display, aliases in SKILL_ALIASES.items():
        if display in skill_keywords:
            continue
        if any(_alias_present(job_description, alias) for alias in aliases):
            skill_keywords.append(display)

    english_terms = re.findall(r"\b[A-Za-z][A-Za-z0-9+#.]{1,24}\b", job_description)
    generic = [
        term
        for term in english_terms
        if term.lower()
        not in {
            "and",
            "with",
            "for",
            "the",
            "job",
            "api",
            "you",
            "are",
            "our",
            "will",
        }
    ]

    chinese_terms = []
    for token in ("后端", "前端", "算法", "数据分析", "微服务", "高并发", "爬虫", "推荐系统", "权限", "支付"):
        if token in job_description:
            chinese_terms.append(token)

    return _unique(skill_keywords + generic + chinese_terms)[:50]


def _keyword_in_resume(keyword: str, resume_keywords: list[str], resume_text: str) -> bool:
    keyword_lower = keyword.lower()
    if any(keyword_lower == item.lower() for item in resume_keywords):
        return True
    return keyword_lower in resume_text.lower()


def _ratio_score(matched: int, total: int, default: float) -> float:
    if total <= 0:
        return default
    return min(100.0, matched / total * 100)


def _experience_score(profile: ResumeProfile, job_description: str) -> float:
    required = _required_years(job_description)
    if required is None:
        return 75.0
    actual = profile.background_info.years_of_experience
    if actual is None:
        return 45.0
    if actual >= required:
        return 100.0
    if actual >= required * 0.7:
        return 75.0
    if actual >= required * 0.4:
        return 55.0
    return 30.0


def _required_years(text: str) -> float | None:
    patterns = (
        r"(\d+(?:\.\d+)?)\s*年(?:以上)?(?:工作|开发|项目)?经验",
        r"经验\s*(\d+(?:\.\d+)?)\s*年",
    )
    values = []
    for pattern in patterns:
        values.extend(float(item) for item in re.findall(pattern, text))
    return max(values) if values else None


def _education_score(profile: ResumeProfile, job_description: str) -> float:
    required = _degree_level(job_description)
    if required is None:
        return 75.0
    actual = _degree_level(profile.background_info.education or "")
    if actual is None:
        return 45.0
    return 100.0 if actual >= required else max(35.0, actual / required * 75)


def _degree_level(text: str) -> int | None:
    found = [level for degree, level in DEGREE_ORDER.items() if degree in text]
    return max(found) if found else None


def _coverage_score(resume_text: str, job_description: str) -> float:
    job_tokens = set(_normalized_tokens(job_description))
    if not job_tokens:
        return 70.0
    resume_tokens = set(_normalized_tokens(resume_text))
    return min(100.0, len(job_tokens & resume_tokens) / len(job_tokens) * 100)


def _normalized_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,24}|[\u4e00-\u9fa5]{2,8}", text)
    stop_words = {"负责", "熟悉", "掌握", "岗位", "要求", "经验", "能力", "相关", "优先"}
    return [token.lower() for token in tokens if token not in stop_words]


def _build_explanation(matched: list[str], missing: list[str], experience_score: float) -> str:
    matched_text = "、".join(matched[:6]) if matched else "暂无明显技能命中"
    missing_text = "、".join(missing[:4]) if missing else "关键技能覆盖较完整"
    if experience_score >= 80:
        exp_text = "经验年限较匹配"
    elif experience_score >= 55:
        exp_text = "经验年限接近要求"
    else:
        exp_text = "经验信息不足或低于要求"
    return f"命中：{matched_text}；待补充：{missing_text}；{exp_text}。"


def _recommendation(score: float) -> str:
    if score >= 85:
        return "强烈推荐进入面试"
    if score >= 70:
        return "推荐进入下一轮筛选"
    if score >= 55:
        return "可作为备选候选人"
    return "暂不推荐"


def _coerce_score(value: object) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, score))


def _ai_dimension_scores(value: object) -> MatchDimensionScores | None:
    if not isinstance(value, dict):
        return None
    skill_match = _dimension_score_value(value, "skill_match")
    experience_relevance = _dimension_score_value(value, "experience_relevance")
    education_fit = _dimension_score_value(value, "education_fit")
    keyword_coverage = _dimension_score_value(value, "keyword_coverage")
    if None in (skill_match, experience_relevance, education_fit, keyword_coverage):
        return None
    return MatchDimensionScores(
        skill_match=skill_match,
        experience_relevance=experience_relevance,
        education_fit=education_fit,
        keyword_coverage=keyword_coverage,
    )


def _dimension_score_value(value: dict, key: str) -> float | None:
    score = _coerce_score(value.get(key))
    return round(score, 1) if score is not None else None


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(values: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            results.append(normalized)
    return results
