"""
Configuration management for Holiday Meal Planner.

Handles environment variables, security constraints, and processing limits
with proper validation and type safety.
"""

import os
from typing import Optional, Set, List
from pydantic import validator, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    All settings can be overridden with environment variables prefixed with MEAL_PLANNER_
    """

    # Application metadata
    app_name: str = Field("Holiday Meal Planner", description="Application name")
    app_version: str = Field("0.1.0", description="Application version")
    debug: bool = Field(False, description="Enable debug mode")

    # Web scraping configuration
    request_delay: float = Field(
        2.0,
        description="Delay between web requests in seconds (rate limiting)",
        ge=0.5,
        le=10.0,
    )
    request_timeout: int = Field(
        30,
        description="Web request timeout in seconds",
        ge=5,
        le=120,
    )
    max_response_size: int = Field(
        5 * 1024 * 1024,  # 5MB
        description="Maximum response size in bytes",
        ge=1024,  # 1KB minimum
        le=50 * 1024 * 1024,  # 50MB maximum
    )
    user_agent: str = Field(
        "Holiday-Meal-Planner/0.1.0 (https://github.com/your-org/holiday-meal-planner)",
        description="User agent for web requests",
    )

    # Security constraints
    https_only: bool = Field(True, description="Require HTTPS for all URLs")
    blocked_domains: Set[str] = Field(
        default_factory=lambda: {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
        },
        description="Blocked domains and IP ranges",
    )
    max_redirects: int = Field(
        5,
        description="Maximum number of redirects to follow",
        ge=0,
        le=10,
    )

    # Processing limits
    max_menu_items: int = Field(
        20,
        description="Maximum number of menu items per request",
        ge=1,
        le=50,
    )
    max_ingredients_per_item: int = Field(
        100,
        description="Maximum ingredients per menu item",
        ge=5,
        le=500,
    )
    max_prep_days: int = Field(
        7,
        description="Maximum days in advance for preparation",
        ge=1,
        le=14,
    )
    max_daily_prep_hours: float = Field(
        8.0,
        description="Maximum preparation hours per day",
        ge=1.0,
        le=24.0,
    )

    # NLP configuration
    confidence_threshold: float = Field(
        0.6,
        description="Minimum confidence score for ingredient extraction",
        ge=0.0,
        le=1.0,
    )
    spacy_model: str = Field(
        "en_core_web_sm",
        description="spaCy model for NLP processing",
    )

    # LLM configuration
    llm_base_url: Optional[str] = Field(
        None,
        description="Base URL for LLM API (e.g., https://api.openai.com/v1)",
    )
    llm_auth_token: Optional[str] = Field(
        None,
        description="Authentication token for LLM API",
    )
    llm_model: str = Field(
        "test",
        description="LLM model name (e.g., gpt-3.5-turbo, claude-3-sonnet, or 'test' for demo mode)",
    )

    # Legacy OpenAI support (deprecated - use LLM_* env vars instead)
    openai_api_key: Optional[str] = Field(
        None,
        description="OpenAI API key (deprecated - use LLM_AUTH_TOKEN)",
    )

    # Logging configuration
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s",
        description="Log format string",
    )
    enable_request_logging: bool = Field(
        True,
        description="Enable detailed request/response logging",
    )

    # Performance settings
    async_pool_size: int = Field(
        10,
        description="Size of async task pool",
        ge=1,
        le=50,
    )
    cache_enabled: bool = Field(
        True,
        description="Enable in-memory caching",
    )
    cache_ttl_seconds: int = Field(
        300,  # 5 minutes
        description="Cache time-to-live in seconds",
        ge=60,
        le=3600,
    )

    # API configuration
    api_host: str = Field("0.0.0.0", description="API host")
    api_port: int = Field(8000, description="API port", ge=1024, le=65535)
    api_workers: int = Field(1, description="Number of API workers", ge=1, le=10)
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins",
    )
    api_key_header: str = Field("X-API-Key", description="API key header name")

    # Development settings
    reload: bool = Field(False, description="Enable auto-reload for development")
    docs_enabled: bool = Field(True, description="Enable API documentation")

    class Config:
        """Pydantic configuration."""

        env_prefix = "MEAL_PLANNER_"
        case_sensitive = False
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level is recognized."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @validator("blocked_domains")
    def validate_blocked_domains(cls, v):
        """Ensure blocked domains is a set."""
        if isinstance(v, list):
            return set(v)
        return v

    @validator("spacy_model")
    def validate_spacy_model(cls, v):
        """Validate spaCy model name format."""
        valid_models = {"en_core_web_sm", "en_core_web_md", "en_core_web_lg"}
        if v not in valid_models:
            # Allow custom models but warn
            pass
        return v

    def is_url_allowed(self, url: str) -> bool:
        """
        Check if a URL is allowed by security policy.

        Args:
            url: URL to check

        Returns:
            True if URL is allowed, False otherwise
        """
        # Check HTTPS requirement
        if self.https_only and not url.startswith("https://"):
            return False

        # Check against blocked domains
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            domain = parsed.hostname

            if domain in self.blocked_domains:
                return False

            # Check for private IP ranges (basic check)
            if domain and any(
                domain.startswith(blocked) for blocked in self.blocked_domains
                if "/" not in blocked  # Skip CIDR ranges for now
            ):
                return False

        except Exception:
            # If URL parsing fails, block it
            return False

        return True

    def get_request_headers(self) -> dict:
        """
        Get standard headers for web requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def get_llm_model_config(self) -> str:
        """
        Get LLM model configuration for PydanticAI.

        Returns:
            Model configuration string compatible with PydanticAI
        """
        # If using test mode, return 'test'
        if self.llm_model == "test":
            return "test"

        # If we have a base URL and token, construct custom model config
        if self.llm_base_url and self.llm_auth_token:
            # For custom API endpoints
            return f"openai:{self.llm_model}"

        # For standard OpenAI models
        if self.llm_model.startswith(("gpt-", "o1-")):
            return f"openai:{self.llm_model}"

        # For Anthropic models
        if self.llm_model.startswith(("claude-", "anthropic.")):
            return f"anthropic:{self.llm_model}"

        # Default fallback
        return self.llm_model


class DevelopmentSettings(Settings):
    """Development-specific settings with relaxed constraints."""

    debug: bool = True
    reload: bool = True
    log_level: str = "DEBUG"
    request_delay: float = 1.0  # Faster for development
    confidence_threshold: float = 0.5  # Lower threshold for testing


class ProductionSettings(Settings):
    """Production-specific settings with strict constraints."""

    debug: bool = False
    reload: bool = False
    log_level: str = "INFO"
    docs_enabled: bool = False  # Disable docs in production
    request_delay: float = 2.5  # More conservative rate limiting


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings singleton.

    Returns:
        Settings instance
    """
    global _settings

    if _settings is None:
        environment = os.getenv("MEAL_PLANNER_ENVIRONMENT", "development").lower()

        if environment == "production":
            _settings = ProductionSettings()
        elif environment == "development":
            _settings = DevelopmentSettings()
        else:
            _settings = Settings()

    return _settings


def override_settings(settings: Settings) -> None:
    """
    Override global settings (useful for testing).

    Args:
        settings: New settings instance
    """
    global _settings
    _settings = settings


# Security utilities

def validate_url_security(url: str, settings: Optional[Settings] = None) -> None:
    """
    Validate URL against security policy.

    Args:
        url: URL to validate
        settings: Settings instance (uses global if None)

    Raises:
        SecurityError: If URL violates security policy
    """
    from .exceptions import SecurityError

    if settings is None:
        settings = get_settings()

    if not settings.is_url_allowed(url):
        raise SecurityError(
            f"URL blocked by security policy: {url}",
            security_check="url_validation",
            blocked_value=url,
        )


def get_safe_request_config(settings: Optional[Settings] = None) -> dict:
    """
    Get safe configuration for web requests.

    Args:
        settings: Settings instance (uses global if None)

    Returns:
        Configuration dictionary for requests
    """
    if settings is None:
        settings = get_settings()

    return {
        "timeout": settings.request_timeout,
        "headers": settings.get_request_headers(),
        "max_redirects": settings.max_redirects,
        "verify": True,  # Always verify SSL certificates
        "stream": False,  # Don't stream large responses
    }