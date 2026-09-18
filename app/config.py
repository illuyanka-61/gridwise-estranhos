"""Configuration management using Pydantic Settings with automatic Gemini provider detection."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and configuration parameters."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server Configuration
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # LLM Settings
    LLM_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    LLM_MODEL: str = "gemini-3.6-flash"
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    LLM_TIMEOUT_SECONDS: float = 15.0

    # Optimization parameters
    PEAK_PENALTY_WEIGHT: float = 0.0  # Default to pure cost optimization matching competition rubric

    @property
    def effective_api_key(self) -> str | None:
        """Returns the active API key, preferring GEMINI_API_KEY if provided."""
        if self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip():
            return self.GEMINI_API_KEY.strip().strip('"').strip("'")
        if self.LLM_API_KEY and self.LLM_API_KEY.strip():
            return self.LLM_API_KEY.strip().strip('"').strip("'")
        return None

    @property
    def effective_base_url(self) -> str:
        """Returns base URL, automatically resolving to Google Gemini if a Gemini key/model is used."""
        key = self.effective_api_key
        if (key and (key.startswith("AIza") or key.startswith("AQ."))) or "gemini" in self.LLM_MODEL.lower():
            if "openai.com" in self.LLM_BASE_URL:
                return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return self.LLM_BASE_URL

    @property
    def effective_model(self) -> str:
        """Returns the active model name."""
        key = self.effective_api_key
        if (key and (key.startswith("AIza") or key.startswith("AQ."))) and "gpt" in self.LLM_MODEL.lower():
            return "gemini-3.6-flash"
        return self.LLM_MODEL


settings = Settings()
