from __future__ import annotations

import re

from backend.app.models.schemas import Section


SECTION_TITLES = {
    "basic": ("基本信息", "个人信息", "个人资料", "联系方式", "profile"),
    "education": ("教育经历", "教育背景", "学历背景", "education"),
    "work": ("工作经历", "实习经历", "工作经验", "experience"),
    "project": ("项目经历", "项目经验", "projects"),
    "skills": ("技能", "专业技能", "技能清单", "skills"),
    "awards": ("获奖", "证书", "荣誉", "certificates"),
}


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    lines = [line.strip(" -\t") for line in text.splitlines()]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line
        if blank and previous_blank:
            continue
        compact_lines.append(line)
        previous_blank = blank
    cleaned = "\n".join(compact_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def split_sections(text: str) -> list[Section]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    heading_map: dict[str, str] = {}
    for canonical, titles in SECTION_TITLES.items():
        for title in titles:
            heading_map[title.lower()] = canonical

    sections: list[Section] = []
    current_title = "全文"
    current_lines: list[str] = []

    for line in lines:
        normalized = re.sub(r"[:：\s]+$", "", line).lower()
        matched = next(
            (title for title in heading_map if normalized == title or normalized.startswith(title)),
            None,
        )
        looks_like_heading = matched is not None and len(line) <= 24
        if looks_like_heading:
            if current_lines:
                sections.append(Section(title=current_title, content="\n".join(current_lines)))
            current_title = line.strip(":： ")
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(Section(title=current_title, content="\n".join(current_lines)))
    return sections[:12]

