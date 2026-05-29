from __future__ import annotations

import re
from typing import Any

from backend.app.core.config import Settings
from backend.app.models.schemas import (
    BackgroundInfo,
    BasicInfo,
    JobInfo,
    ProjectExperience,
    ResumeProfile,
)
from backend.app.services.ai_client import AIClient


SKILL_ALIASES = {
    "Python": ("python",),
    "Java": ("java",),
    "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript", "ts"),
    "Go": ("golang", " go "),
    "C++": ("c++", "cpp"),
    "FastAPI": ("fastapi",),
    "Flask": ("flask",),
    "Django": ("django",),
    "Spring Boot": ("spring boot", "springboot"),
    "React": ("react",),
    "Vue": ("vue", "vue.js"),
    "Node.js": ("node.js", "nodejs", "node "),
    "MySQL": ("mysql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "MongoDB": ("mongodb",),
    "Redis": ("redis",),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Linux": ("linux",),
    "Git": ("git",),
    "RESTful API": ("restful", "rest api"),
    "Serverless": ("serverless", "函数计算", "fc"),
    "阿里云": ("阿里云", "aliyun"),
    "AWS": ("aws",),
    "NLP": ("nlp", "自然语言处理"),
    "LLM": ("llm", "大模型", "大语言模型"),
    "LangChain": ("langchain",),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "机器学习": ("机器学习", "machine learning"),
    "深度学习": ("深度学习", "deep learning"),
}


class ResumeExtractor:
    def __init__(self, settings: Settings) -> None:
        self.ai_client = AIClient(settings)

    async def extract(self, text: str) -> ResumeProfile:
        heuristic_profile = self._heuristic_extract(text)
        ai_data = await self.ai_client.extract_resume(text)
        if not ai_data:
            return heuristic_profile
        return self._merge_ai_data(heuristic_profile, ai_data, text)

    def _heuristic_extract(self, text: str) -> ResumeProfile:
        email = _first_match(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
        phone = _first_match(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", text)
        name = _extract_name(text)
        wechat = _extract_labeled_value(text, ("微信", "WeChat"))
        github = _extract_url_value(text, ("GitHub", "Github"))
        blog = _extract_url_value(text, ("博客", "个人主页", "Blog"))
        address = _extract_labeled_value(
            text,
            ("地址", "现居住地", "所在地", "居住地", "意向城市", "Address"),
        )
        expected_salary = _extract_salary(text)
        job_intention = _extract_labeled_value(
            text,
            ("求职意向", "应聘岗位", "目标岗位", "意向岗位", "意向职位", "期望职位"),
        )
        years = _extract_years(text)
        education = _extract_education(text)
        skills = extract_skills(text)

        return ResumeProfile(
            basic_info=BasicInfo(
                name=name,
                phone=phone,
                email=email,
                address=address,
                wechat=wechat,
                github=github,
                blog=blog,
            ),
            job_info=JobInfo(job_intention=job_intention, expected_salary=expected_salary),
            background_info=BackgroundInfo(
                years_of_experience=years,
                education=education,
                work_experience=_extract_bullets(text, ("工作经历", "实习经历", "工作经验"), limit=5),
                project_experiences=_extract_projects(text, skills),
                skills=skills,
            ),
            summary=_build_summary(name, job_intention, years, education, skills),
            extraction_source="heuristic",
        )

    def _merge_ai_data(
        self,
        fallback: ResumeProfile,
        data: dict[str, Any],
        source_text: str,
    ) -> ResumeProfile:
        basic = data.get("basic_info") if isinstance(data.get("basic_info"), dict) else {}
        job = data.get("job_info") if isinstance(data.get("job_info"), dict) else {}
        background = (
            data.get("background_info") if isinstance(data.get("background_info"), dict) else {}
        )

        ai_projects = background.get("project_experiences") or []
        projects = []
        if isinstance(ai_projects, list):
            for item in ai_projects[:8]:
                if isinstance(item, dict):
                    projects.append(ProjectExperience(**item))

        skills = _validated_skills(
            list(background.get("skills") or []) + fallback.background_info.skills,
            source_text,
        )
        projects = _choose_project_experiences(
            projects,
            fallback.background_info.project_experiences,
        )

        return ResumeProfile(
            basic_info=BasicInfo(
                name=basic.get("name") or fallback.basic_info.name,
                phone=basic.get("phone") or fallback.basic_info.phone,
                email=basic.get("email") or fallback.basic_info.email,
                address=basic.get("address") or fallback.basic_info.address,
                wechat=basic.get("wechat") or fallback.basic_info.wechat,
                github=basic.get("github") or fallback.basic_info.github,
                blog=basic.get("blog") or fallback.basic_info.blog,
            ),
            job_info=JobInfo(
                job_intention=job.get("job_intention") or fallback.job_info.job_intention,
                expected_salary=job.get("expected_salary") or fallback.job_info.expected_salary,
            ),
            background_info=BackgroundInfo(
                years_of_experience=background.get("years_of_experience")
                or fallback.background_info.years_of_experience,
                education=background.get("education") or fallback.background_info.education,
                work_experience=background.get("work_experience")
                or fallback.background_info.work_experience,
                project_experiences=projects or fallback.background_info.project_experiences,
                skills=skills,
            ),
            summary=data.get("summary") or fallback.summary,
            extraction_source="ai",
        )


def extract_skills(text: str) -> list[str]:
    skills = []
    for display, aliases in SKILL_ALIASES.items():
        if any(_alias_present(text, alias) for alias in aliases):
            skills.append(display)
    return skills


def _alias_present(text: str, alias: str) -> bool:
    alias = alias.strip()
    if not alias:
        return False
    if re.search(r"[\u4e00-\u9fa5]", alias):
        return alias in text
    if alias.lower() == "react":
        return re.search(r"(?<![A-Za-z0-9+#.])React(?![A-Za-z0-9+#.])", text) is not None
    if re.fullmatch(r"[A-Za-z0-9.+#-]+(?: [A-Za-z0-9.+#-]+)*", alias):
        pattern = rf"(?<![A-Za-z0-9+#.]){re.escape(alias)}(?![A-Za-z0-9+#.])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return alias.lower() in text.lower()


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0).strip() if match else None


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n|，,;；]{{2,80}})"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_url_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]?\s*(https?://[^\s，,;；|]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip("。")
    return None


def _extract_name(text: str) -> str | None:
    labeled = _extract_labeled_value(text, ("姓名", "Name"))
    if labeled:
        return labeled.split()[0][:30]

    for line in [item.strip() for item in text.splitlines() if item.strip()][:12]:
        if any(token in line for token in ("简历", "电话", "邮箱", "求职", "个人信息")):
            continue
        if re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", line):
            return line
        if re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+){0,3}", line):
            return line
    return None


def _extract_salary(text: str) -> str | None:
    labeled = _extract_labeled_value(text, ("期望薪资", "薪资要求", "期望月薪"))
    if labeled:
        return labeled
    return _first_match(r"\d{1,3}\s*[kK千]\s*(?:[-~至]\s*\d{1,3}\s*[kK千])?", text)


def _extract_years(text: str) -> float | None:
    patterns = (
        r"(\d+(?:\.\d+)?)\s*年(?:以上)?(?:工作|开发|项目)?经验",
        r"工作年限\s*[:：]\s*(\d+(?:\.\d+)?)\s*年",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def _extract_education(text: str) -> str | None:
    degree_pattern = r"(博士|硕士|研究生|本科|学士|大专|专科)"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    education_lines = _education_section_lines(lines, degree_pattern)
    if not education_lines:
        education_lines = [
            line
            for line in lines
            if re.search(degree_pattern, line) and not _looks_like_award_line(line)
        ]
    if education_lines:
        return "；".join(_format_education_line(line) for line in education_lines[:3])
    return None


def _format_education_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    date_pattern = r"\d{4}\.\d{1,2}\s*[-–—至]\s*\d{4}\.\d{1,2}"
    degree_pattern = r"博士|硕士|研究生|本科|学士|大专|专科"
    line = re.sub(rf"(?<=[\u4e00-\u9fa5])({date_pattern})", r" \1", line)
    line = re.sub(rf"({date_pattern})({degree_pattern})", r"\1 \2", line)
    line = re.sub(rf"({degree_pattern})(?=[\u4e00-\u9fa5A-Za-z])", r"\1 ", line)
    return re.sub(r"\s+", " ", line).strip()


def _education_section_lines(lines: list[str], degree_pattern: str) -> list[str]:
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.search(r"教育经历|教育背景|学历背景|Education", line, flags=re.IGNORECASE)
        ),
        None,
    )
    if start is None:
        return []

    stop_pattern = re.compile(
        r"工作经历|实习经历|项目经历|项目经验|专业技能|技能清单|技能|获奖|奖项|荣誉|证书|自我评价|Experience|Projects|Skills",
        flags=re.IGNORECASE,
    )
    results: list[str] = []
    for line in lines[start + 1 :]:
        if stop_pattern.search(line) and len(line) <= 18:
            break
        if re.search(degree_pattern, line) and not _looks_like_award_line(line):
            results.append(line)
        elif results and not _looks_like_award_line(line) and len(line) <= 80:
            if not stop_pattern.search(line):
                results[-1] = f"{results[-1]} {line}"
        if len(results) >= 3:
            break
    return results


def _looks_like_award_line(line: str) -> bool:
    award_words = ("奖", "获奖", "荣誉", "证书", "奖学金", "竞赛", "比赛", "大赛", "优秀", "三好")
    return any(word in line for word in award_words)


def _extract_bullets(text: str, headings: tuple[str, ...], limit: int) -> list[str]:
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    start = next((i for i, line in enumerate(lines) if any(h in line for h in headings)), None)
    if start is None:
        return []
    results: list[str] = []
    stop_words = ("教育", "项目", "技能", "证书", "荣誉")
    for line in lines[start + 1 :]:
        if any(word in line for word in stop_words) and len(line) <= 12:
            break
        if 8 <= len(line) <= 160:
            results.append(line)
        if len(results) >= limit:
            break
    return results


def _extract_projects(text: str, skills: list[str]) -> list[ProjectExperience]:
    blocks = _extract_project_blocks(text)
    if blocks:
        projects: list[ProjectExperience] = []
        for block in blocks[:8]:
            header = block[0]
            detail_lines = block[1:]
            name, role = _parse_project_header(header)
            description = "\n".join(_normalize_project_detail(line) for line in detail_lines)
            description = description.strip() or header
            technologies = [
                skill
                for skill in skills
                if any(_alias_present("\n".join(block), alias) for alias in SKILL_ALIASES.get(skill, (skill,)))
            ]
            projects.append(
                ProjectExperience(
                    name=name,
                    role=role,
                    description=description,
                    technologies=technologies,
                )
            )
        return projects

    lines = _extract_bullets(text, ("项目经历", "项目经验", "Projects"), limit=12)
    projects: list[ProjectExperience] = []
    for line in lines[:5]:
        technologies = [skill for skill in skills if skill.lower() in line.lower()]
        projects.append(
            ProjectExperience(
                name=line[:36],
                description=line,
                technologies=technologies,
            )
        )
    return projects


def _extract_project_blocks(text: str) -> list[list[str]]:
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(r"项目经历|项目经验|Projects", line, flags=re.IGNORECASE)
        ),
        None,
    )
    if start is None:
        return []

    stop_pattern = re.compile(
        r"教育经历|教育背景|专业技能|技能清单|工作经历|实习经历|奖项|获奖|荣誉|证书|自我评价|Education|Skills|Awards",
        flags=re.IGNORECASE,
    )

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines[start + 1 :]:
        if stop_pattern.fullmatch(line) or (stop_pattern.search(line) and len(line) <= 14):
            break
        if _is_project_header(line):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _is_project_header(line: str) -> bool:
    if _looks_like_project_detail_name(line):
        return False
    has_date_range = re.search(r"\d{4}\.\d{1,2}\s*[-–—至]\s*(?:\d{4}\.\d{1,2}|至今)", line)
    has_url = re.search(r"https?://|github\.com", line, flags=re.IGNORECASE)
    has_role = re.search(r"(负责人|开发|工程师|成员|主程|全栈|前端|后端)", line)
    return bool((has_date_range and has_role) or (has_url and has_role) or (has_url and has_date_range))


def _parse_project_header(header: str) -> tuple[str, str | None]:
    cleaned = re.sub(r"\s+", " ", header).strip()
    without_url = re.sub(r"https?://\S+", "", cleaned).strip()
    without_url = re.sub(r"链接\s*[:：]?\s*$", "", without_url).strip()
    without_date = re.sub(r"\d{4}\.\d{1,2}\s*[-–—至]\s*(?:\d{4}\.\d{1,2}|至今)", "", without_url).strip()

    role_match = re.search(r"(前端负责人|后端负责人|全栈开发|前端开发|后端开发|独立开发|负责人|开发工程师|成员)$", without_date)
    role = role_match.group(1) if role_match else None
    name = without_date[: role_match.start()].strip() if role_match else without_date
    name = name.strip(" ，,")
    return (name or cleaned[:42], role)


def _normalize_project_detail(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[\uf06c●•\-]\s*", "", line)
    return line


def _looks_like_project_detail_name(name: str) -> bool:
    detail_prefixes = (
        "技术栈",
        "技术栈和框架",
        "项目描述",
        "主要工作",
        "项目成就",
        "负责",
        "对接",
        "参与",
        "适配",
        "设计",
        "搭建",
        "实现",
        "基于",
    )
    return name.strip().startswith(detail_prefixes)


def _choose_project_experiences(
    ai_projects: list[ProjectExperience],
    fallback_projects: list[ProjectExperience],
) -> list[ProjectExperience]:
    if not ai_projects:
        return fallback_projects
    detail_like_count = sum(
        1 for project in ai_projects if _looks_like_project_detail_name(project.name or "")
    )
    if detail_like_count or (
        fallback_projects and len(ai_projects) > max(3, len(fallback_projects) + 1)
    ):
        return fallback_projects
    return ai_projects


def _build_summary(
    name: str | None,
    job_intention: str | None,
    years: float | None,
    education: str | None,
    skills: list[str],
) -> str:
    parts = []
    if name:
        parts.append(f"候选人{name}")
    if job_intention:
        parts.append(f"求职意向为{job_intention}")
    if years is not None:
        parts.append(f"约{years:g}年经验")
    if education:
        parts.append(f"学历背景：{education}")
    if skills:
        parts.append("技能：" + "、".join(skills[:10]))
    return "；".join(parts) if parts else "已完成基础简历解析。"


def _unique_strings(values: list[Any]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = value.strip()
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            results.append(normalized)
    return results


def _validated_skills(values: list[Any], source_text: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        skill = value.strip()
        aliases = SKILL_ALIASES.get(skill, (skill,))
        if not any(_alias_present(source_text, alias) for alias in aliases):
            continue
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            results.append(skill)
    return results
