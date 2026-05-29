from __future__ import annotations

import json
import re
from typing import Any

import httpx

from backend.app.core.config import Settings
from backend.app.models.schemas import ResumeProfile


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.resolved_ai_api_key)

    async def extract_resume(self, text: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        prompt = (
            "你是招聘系统中的简历解析助手。请只返回 JSON，不要 Markdown。\n"
            "字段结构：basic_info{name,phone,email,address,wechat,github,blog}, "
            "job_info{job_intention,expected_salary}, "
            "background_info{years_of_experience,education,work_experience,project_experiences,skills}, "
            "summary。\n"
            "project_experiences 中每项包含 name, role, description, technologies。\n"
            "请完整保留项目技术栈中明确出现的框架、库、工具和语言，例如 Nuxt、Vue3、Pinia、"
            "TailwindCSS、ElementPlus、AntDesign、Node.js、Electron 等，不要只抽取通用语言。\n"
            "skills 必须来自简历原文明确出现的技能词，不要根据项目内容自行推断；"
            "不要把 JavaScript 拆成 Java；不要把 LangChain ReAct Agent 识别成 React 前端框架。"
            "education 只填写学校、学历、专业、时间等教育背景，不要混入奖项、荣誉、证书。\n"
            "无法判断的字段使用 null 或空数组。\n\n"
            f"简历文本：\n{text[:12000]}"
        )
        content = await self._chat(prompt, temperature=0.1)
        return _parse_json_object(content) if content else None

    async def analyze_resume_and_match(
        self,
        text: str,
        job_description: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        prompt = (
            "你是招聘系统中的简历解析与岗位匹配助手。请只返回 JSON，不要 Markdown。\n"
            "输出字段：resume, match。\n"
            "resume 字段结构：basic_info{name,phone,email,address,wechat,github,blog}, "
            "job_info{job_intention,expected_salary}, "
            "background_info{years_of_experience,education,work_experience,project_experiences,skills}, "
            "summary。\n"
            "project_experiences 中每项包含 name, role, description, technologies。"
            "请完整保留项目技术栈中明确出现的框架、库、工具和语言，例如 Nuxt、Vue3、Pinia、"
            "TailwindCSS、ElementPlus、AntDesign、Node.js、Electron 等。\n"
            "match 字段结构：score(0-100), recommendation, explanation(不超过120字), "
            "dimension_scores{skill_match,experience_relevance,education_fit,keyword_coverage}, "
            "matched_keywords(array), missing_keywords(array), resume_keywords(array), job_keywords(array)。\n"
            "评分必须基于简历原文和岗位描述。JavaScript 不等于 Java；"
            "LangChain ReAct Agent 不等于 React 前端框架。无法判断的字段使用 null 或空数组。\n\n"
            f"简历 OCR/文本原文：\n{text[:14000]}\n\n"
            f"岗位描述：\n{job_description[:6000]}"
        )
        content = await self._chat(prompt, temperature=0.15)
        return _parse_json_object(content) if content else None

    async def score_match(
        self,
        resume_text: str,
        profile: ResumeProfile,
        job_description: str,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        profile_json = json.dumps(profile.model_dump(mode="json"), ensure_ascii=False)
        prompt = (
            "你是严谨的招聘匹配评分助手。请只返回 JSON，不要 Markdown。\n"
            "输出字段：score(0-100), recommendation, explanation(不超过120字), "
            "dimension_scores{skill_match,experience_relevance,education_fit,keyword_coverage}, "
            "matched_keywords(array), missing_keywords(array), resume_keywords(array), job_keywords(array)。\n"
            "评分必须基于简历原文和岗位描述，不要只依赖后端规则抽出的技能列表。"
            "如果岗位要求与候选人方向明显不一致，应给低分；如果岗位描述命中项目技术栈和职责，应给合理高分。"
            "JavaScript 不等于 Java；LangChain ReAct Agent 不等于 React 前端框架。\n\n"
            f"结构化简历：\n{profile_json[:8000]}\n\n"
            f"简历 OCR/文本原文：\n{resume_text[:12000]}\n\n"
            f"岗位描述：\n{job_description[:6000]}"
        )
        content = await self._chat(prompt, temperature=0.2)
        return _parse_json_object(content) if content else None

    async def _chat(self, prompt: str, temperature: float) -> str | None:
        url = self.settings.resolved_ai_api_base.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.resolved_ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.resolved_ai_model,
            "messages": [
                {"role": "system", "content": "You output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception:
            return None


def _parse_json_object(content: str) -> dict[str, Any] | None:
    content = content.strip()
    content = re.sub(r"^```(?:json)?", "", content).strip()
    content = re.sub(r"```$", "", content).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or start >= end:
        return None
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
