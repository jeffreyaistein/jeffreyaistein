"""
Jeffrey AIstein - Configuration
Environment-based settings management
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Core
    debug: bool = False
    log_level: str = "info"

    # Database
    database_url: str = "postgresql://aistein:aistein_dev_password@localhost:5432/aistein"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-3-5-sonnet-20241022"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-ada-002"

    # TTS
    tts_provider: str = "elevenlabs"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_monolingual_v1"
    elevenlabs_output_format: str = "mp3_44100_128"
    tts_max_text_length: int = 1000  # Max characters per TTS request
    tts_rate_limit_per_minute: int = 10  # Rate limit for TTS requests

    # Image Generation
    image_gen_provider: str = "openai"
    replicate_api_token: str = ""

    # X (Twitter)
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_bearer_token: str = ""
    x_bot_user_id: str = ""
    x_bot_enabled: bool = False
    safe_mode: bool = False
    approval_required: bool = True
    x_hourly_post_limit: int = 5
    x_daily_post_limit: int = 20

    # Token Data
    token_data_provider: str = "dexscreener"
    token_contract_address: str = ""
    token_chain: str = "solana"
    coingecko_api_key: str = ""
    helius_api_key: str = ""
    helius_rpc_url: str = ""

    # Embeddings
    voyage_api_key: str = ""

    # Monitoring
    sentry_dsn: str = ""

    # Security
    secret_key: str = "CHANGE_THIS"
    session_secret: str = "CHANGE_THIS"
    admin_api_key: str = "CHANGE_THIS"
    cors_origins: str = "http://localhost:3000"

    # Rate Limiting
    chat_rate_limit_per_minute: int = 20
    api_rate_limit_per_minute: int = 100

    # Feature Flags
    enable_tts: bool = True
    enable_x_bot: bool = False
    enable_image_gen: bool = True
    enable_token_data: bool = True

    # Self-Style Pipeline
    # IMPORTANT: Proposals are NEVER auto-activated. Admin approval required.
    self_style_enabled: bool = False  # Enable automatic style proposal generation
    self_style_interval_hours: int = 24  # Hours between proposal generation runs
    self_style_min_tweets: int = 25  # Minimum tweets required to generate proposal
    self_style_max_tweets: int = 500  # Maximum tweets to analyze per proposal
    self_style_days: int = 30  # Days to look back for tweets
    self_style_include_replies: bool = True  # Include reply tweets in analysis

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience accessors
settings = get_settings()
