import asyncio

from backend.app.core.config import Settings
from backend.app.models.schemas import BackgroundInfo, ResumeProfile
from backend.app.services.matcher import ResumeMatcher
from backend.app.services.matcher import _extract_job_keywords


def test_javascript_job_requirement_does_not_add_java():
    keywords = _extract_job_keywords("前端工程师，熟悉HTML、CSS、JavaScript，有 2 年以上项目经验，本科及以上。")
    assert "JavaScript" in keywords
    assert "Java" not in keywords


def test_resume_matcher_scores_core_dimensions():
    profile = ResumeProfile(
        background_info=BackgroundInfo(
            years_of_experience=3,
            education="本科 计算机科学与技术",
            skills=["Python", "FastAPI", "Redis", "Docker"],
        ),
        summary="3年 Python 后端开发经验，熟悉 FastAPI、Redis、Docker。",
    )
    matcher = ResumeMatcher(Settings(_env_file=None, ai_api_key=None, deepseek_api_key=None))
    response = asyncio.run(
        matcher.match(
            resume_id="demo",
            profile=profile,
            resume_text="Python FastAPI Redis Docker 本科 3年经验",
            job_description="Python 后端工程师，熟悉 FastAPI、Redis，有 2 年以上经验，本科及以上。",
        )
    )
    assert response.score >= 70
    assert "Python" in response.matched_keywords
    assert response.dimension_scores.experience_relevance == 100


def test_ai_match_result_is_primary_when_available():
    profile = ResumeProfile(
        background_info=BackgroundInfo(
            education="本科 计算机科学与技术",
            skills=["TypeScript", "React", "Node.js"],
        ),
        summary="前端项目经验，熟悉 TypeScript、React、Node.js。",
    )
    matcher = ResumeMatcher(Settings(_env_file=None, ai_api_key=None, deepseek_api_key=None))

    class FakeAIClient:
        async def score_match(self, resume_text, profile, job_description):
            return {
                "score": 88,
                "recommendation": "推荐进入下一轮筛选",
                "explanation": "岗位技术栈与项目经历高度匹配。",
                "dimension_scores": {
                    "skill_match": 90,
                    "experience_relevance": 85,
                    "education_fit": 100,
                    "keyword_coverage": 80,
                },
                "matched_keywords": ["TypeScript", "React", "Node.js"],
                "missing_keywords": [],
                "resume_keywords": ["TypeScript", "React", "Node.js"],
                "job_keywords": ["TypeScript", "React", "Node.js"],
            }

    matcher.ai_client = FakeAIClient()
    response = asyncio.run(
        matcher.match(
            resume_id="demo",
            profile=profile,
            resume_text="TypeScript React Node.js 本科",
            job_description="前端工程师，熟悉 TypeScript、React、Node.js，本科及以上。",
        )
    )

    assert response.score == 88
    assert response.dimension_scores.skill_match == 90
    assert response.matched_keywords == ["TypeScript", "React", "Node.js"]
