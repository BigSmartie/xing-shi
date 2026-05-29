from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "AI Resume Analyzer"
    api_prefix: str = "/api/v1"
    environment: Literal["local", "serverless", "production"] = "local"

    max_upload_mb: int = Field(default=8, ge=1, le=50)
    cache_dir: Path = Path(".cache")

    cors_origins: list[str] = ["*"]

    enable_ocr: bool = True
    ocr_provider: Literal["rapidocr", "none"] = "rapidocr"
    ocr_render_dpi: int = Field(default=260, ge=96, le=300)
    ocr_max_pages: int = Field(default=5, ge=1, le=20)

    ai_provider: Literal["deepseek", "dashscope", "custom"] = "deepseek"
    ai_api_key: str | None = None
    ai_api_base: str | None = None
    ai_model: str | None = None
    deepseek_api_key: str | None = None
    dashscope_api_key: str | None = None
    ai_timeout_seconds: int = Field(default=25, ge=5, le=120)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_ai_api_key(self) -> str | None:
        if self.ai_api_key:
            return self.ai_api_key
        if self.ai_provider == "deepseek":
            return self.deepseek_api_key
        if self.ai_provider == "dashscope":
            return self.dashscope_api_key
        return None

    @property
    def resolved_ai_api_base(self) -> str:
        if self.ai_api_base:
            return self.ai_api_base
        if self.ai_provider == "dashscope":
            return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return "https://api.deepseek.com"

    @property
    def resolved_ai_model(self) -> str:
        if self.ai_model:
            return self.ai_model
        if self.ai_provider == "dashscope":
            return "qwen-plus"
        return "deepseek-chat"


def get_settings() -> Settings:
    return Settings()
