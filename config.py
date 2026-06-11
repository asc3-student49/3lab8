"""
Configuration Management
Type-safe configuration with Pydantic Settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, Literal
import logging
import os


class Settings(BaseSettings):
    """
    Application configuration with type safety and validation.

    Automatically loads from environment variables and .env file.
    Uses Pydantic's validation to ensure configuration correctness.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )

    # ===== Application Settings =====
    app_name: str = "agent-service"
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # ===== OpenAI Configuration =====
    openai_api_key: str = Field(
        ..., min_length=1, description="OpenAI API key"  # Required field
    )
    ai_model: str = Field(default="openai:gpt-5.4-mini", description="AI model to use")

    # ===== Database Configuration =====
    database_url: str = Field(
        default="sqlite:///:memory:", description="Database connection URL"
    )
    database_pool_size: int = Field(
        default=10, ge=1, le=100, description="Database connection pool size"
    )
    database_timeout: float = Field(
        default=30.0, gt=0, description="Database query timeout in seconds"
    )
    database_max_overflow: int = Field(
        default=20, ge=0, description="Max connections beyond pool size"
    )

    # ===== Redis Cache Configuration =====
    redis_host: str = Field(default="localhost", description="Redis server host")
    redis_port: int = Field(
        default=6379, ge=1, le=65535, description="Redis server port"
    )
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis database number")
    redis_password: Optional[str] = Field(
        default=None, description="Redis password (if required)"
    )
    redis_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")

    # ===== HTTP Client Configuration =====
    http_timeout: float = Field(
        default=30.0, gt=0, description="HTTP request timeout in seconds"
    )
    http_max_connections: int = Field(
        default=100, ge=1, description="Maximum concurrent connections"
    )
    http_max_keepalive: int = Field(
        default=20, ge=1, description="Maximum keepalive connections"
    )

    # ===== Feature Flags =====
    enable_caching: bool = Field(default=True, description="Enable response caching")
    enable_retries: bool = Field(
        default=True, description="Enable automatic retries on failure"
    )
    max_retries: int = Field(
        default=3, ge=0, le=10, description="Maximum retry attempts"
    )
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    # ===== Security =====
    api_key_required: bool = Field(
        default=False, description="Require API key for requests"
    )
    allowed_origins: list[str] = Field(
        default=["*"], description="CORS allowed origins"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is valid."""
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    def configure_logging(self):
        """
        Configure application logging based on settings.

        Sets log level, format, and suppresses noisy libraries.
        """
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            force=True,  # Override existing configuration
        )

        logger = logging.getLogger(__name__)
        logger.info(
            f"Logging configured: level={self.log_level}, env={self.environment}"
        )

        # Suppress noisy loggers in production
        if not self.debug:
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)
            logging.getLogger("urllib3").setLevel(logging.WARNING)

        # Mask sensitive values in logs
        if self.is_production():
            logger.info("Production mode: Sensitive values will be masked")

    def get_masked_config(self) -> dict:
        """
        Get configuration dict with sensitive values masked.

        Returns:
            Dictionary with masked sensitive fields
        """
        config = self.model_dump()

        # Mask sensitive fields
        sensitive_fields = ["openai_api_key", "redis_password", "database_url"]
        for field in sensitive_fields:
            if field in config and config[field]:
                config[field] = "***MASKED***"

        return config

    def validate_production_config(self):
        """
        Validate production-specific requirements.

        Raises:
            ValueError: If production config is invalid
        """
        if not self.is_production():
            return

        errors = []

        # Production must not be in debug mode
        if self.debug:
            errors.append("Debug mode must be disabled in production")

        # Production should use stronger database
        if "sqlite" in self.database_url.lower():
            errors.append(
                "SQLite not recommended for production (use PostgreSQL/MySQL)"
            )

        # Production should have security enabled
        if not self.api_key_required:
            errors.append("API key authentication recommended for production")

        if errors:
            raise ValueError(f"Production configuration errors: {', '.join(errors)}")


def load_config() -> Settings:
    """
    Load and validate configuration.

    Returns:
        Validated Settings instance

    Raises:
        Exception: If configuration is invalid
    """
    try:
        settings = Settings()

        # Configure logging
        settings.configure_logging()

        logger = logging.getLogger(__name__)
        logger.info(f"Configuration loaded successfully: env={settings.environment}")

        # Log masked config in debug mode
        if settings.debug:
            logger.debug(f"Configuration: {settings.get_masked_config()}")

        # Validate production requirements
        if settings.is_production():
            settings.validate_production_config()

        return settings

    except Exception as e:
        logging.error(f"Failed to load configuration: {e}")
        raise


# Example usage
if __name__ == "__main__":
    try:
        config = load_config()

        print("\n" + "=" * 60)
        print("CONFIGURATION")
        print("=" * 60)
        print(f"Environment: {config.environment}")
        print(f"Debug: {config.debug}")
        print(f"Log Level: {config.log_level}")
        print(f"")
        print(f"AI Model: {config.ai_model}")
        print(f"")
        print(f"Database: {config.database_url}")
        print(f"Pool Size: {config.database_pool_size}")
        print(f"")
        print(f"Redis: {config.redis_host}:{config.redis_port}")
        print(f"Cache TTL: {config.redis_ttl}s")
        print(f"")
        print(f"Features:")
        print(f"  - Caching: {config.enable_caching}")
        print(f"  - Retries: {config.enable_retries} (max={config.max_retries})")
        print(f"  - Metrics: {config.enable_metrics}")
        print("=" * 60)

    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
