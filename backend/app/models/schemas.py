from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BasicInfo(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    wechat: str | None = None
    github: str | None = None
    blog: str | None = None


class JobInfo(BaseModel):
    job_intention: str | None = None
    expected_salary: str | None = None


class ProjectExperience(BaseModel):
    name: str | None = None
    role: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class BackgroundInfo(BaseModel):
    years_of_experience: float | None = None
    education: str | None = None
    work_experience: list[str] = Field(default_factory=list)
    project_experiences: list[ProjectExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    basic_info: BasicInfo = Field(default_factory=BasicInfo)
    job_info: JobInfo = Field(default_factory=JobInfo)
    background_info: BackgroundInfo = Field(default_factory=BackgroundInfo)
    summary: str | None = None
    extraction_source: str = "heuristic"


class Section(BaseModel):
    title: str
    content: str


class ResumeAnalysisResponse(BaseModel):
    resume_id: str
    filename: str
    content_hash: str
    page_count: int
    full_text: str
    text_preview: str
    sections: list[Section] = Field(default_factory=list)
    profile: ResumeProfile
    from_cache: bool = False


class MatchDimensionScores(BaseModel):
    skill_match: float
    experience_relevance: float
    education_fit: float
    keyword_coverage: float


class MatchScoreResponse(BaseModel):
    resume_id: str
    score: float
    dimension_scores: MatchDimensionScores
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    resume_keywords: list[str] = Field(default_factory=list)
    job_keywords: list[str] = Field(default_factory=list)
    recommendation: str
    explanation: str
    from_cache: bool = False


class MatchRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=12000)


class AnalyzeAndMatchResponse(BaseModel):
    resume: ResumeAnalysisResponse
    match: MatchScoreResponse | None = None


class ErrorResponse(BaseModel):
    detail: str
    extra: dict[str, Any] | None = None
