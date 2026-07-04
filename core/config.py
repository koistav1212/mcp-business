from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = Field(default="AI Agent Framework")
    DEBUG: bool = Field(default=True)
    API_HOST: str = Field(default="127.0.0.1")
    API_PORT: int = Field(default=8000)

    # LLM Settings
    LLM_PROVIDER: str = Field(default="openrouter")
    OPENAI_API_KEY: str = Field(default="sk-placeholder")
    OPENROUTER_API_KEY: str = Field(default="sk-placeholder")
    GROQ_API_KEY: str = Field(default="sk-placeholder")
    TOGETHER_API_KEY: str = Field(default="sk-placeholder")
    GITHUB_TOKEN: str = Field(default="sk-placeholder")
    NVDA_KEY: str = Field(default="sk-placeholder")
    LLM_MODEL: str = Field(default="gpt-4o")

    # Logging Config
    LOG_LEVEL: str = Field(default="INFO")

# Global settings instance
settings = Settings()
