"""
Custom exception types for Holiday Meal Planner.

Provides structured error handling across the meal planning pipeline
with specific exceptions for different types of failures.
"""

from typing import Optional, Dict, Any


class MealPlannerException(Exception):
    """Base exception for all meal planner errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "MEAL_PLANNER_ERROR"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class RecipeParsingError(MealPlannerException):
    """Raised when recipe extraction or parsing fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        extraction_method: Optional[str] = None,
        http_status: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize recipe parsing error.

        Args:
            message: Error description
            url: URL that failed to parse
            extraction_method: Method that was being used
            http_status: HTTP status code if web request
            details: Additional context
        """
        error_details = details or {}
        if url:
            error_details["url"] = url
        if extraction_method:
            error_details["extraction_method"] = extraction_method
        if http_status:
            error_details["http_status"] = http_status

        super().__init__(
            message=message,
            error_code="RECIPE_PARSING_ERROR",
            details=error_details,
        )


class IngredientConsolidationError(MealPlannerException):
    """Raised when ingredient consolidation fails."""

    def __init__(
        self,
        message: str,
        ingredient_names: Optional[list] = None,
        consolidation_step: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ingredient consolidation error.

        Args:
            message: Error description
            ingredient_names: Names of ingredients that caused the error
            consolidation_step: Which step in consolidation failed
            details: Additional context
        """
        error_details = details or {}
        if ingredient_names:
            error_details["ingredient_names"] = ingredient_names
        if consolidation_step:
            error_details["consolidation_step"] = consolidation_step

        super().__init__(
            message=message,
            error_code="INGREDIENT_CONSOLIDATION_ERROR",
            details=error_details,
        )


class TimelineGenerationError(MealPlannerException):
    """Raised when timeline generation fails."""

    def __init__(
        self,
        message: str,
        scheduling_step: Optional[str] = None,
        conflicting_tasks: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize timeline generation error.

        Args:
            message: Error description
            scheduling_step: Which step in scheduling failed
            conflicting_tasks: Tasks that have conflicts
            details: Additional context
        """
        error_details = details or {}
        if scheduling_step:
            error_details["scheduling_step"] = scheduling_step
        if conflicting_tasks:
            error_details["conflicting_tasks"] = conflicting_tasks

        super().__init__(
            message=message,
            error_code="TIMELINE_GENERATION_ERROR",
            details=error_details,
        )


class ValidationError(MealPlannerException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        invalid_value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize validation error.

        Args:
            message: Error description
            field_name: Name of the field that failed validation
            invalid_value: The value that failed validation
            details: Additional context
        """
        error_details = details or {}
        if field_name:
            error_details["field_name"] = field_name
        if invalid_value is not None:
            error_details["invalid_value"] = str(invalid_value)

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=error_details,
        )


class SecurityError(MealPlannerException):
    """Raised when security validation fails."""

    def __init__(
        self,
        message: str,
        security_check: Optional[str] = None,
        blocked_value: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize security error.

        Args:
            message: Error description
            security_check: Type of security check that failed
            blocked_value: Value that was blocked
            details: Additional context
        """
        error_details = details or {}
        if security_check:
            error_details["security_check"] = security_check
        if blocked_value:
            error_details["blocked_value"] = blocked_value

        super().__init__(
            message=message,
            error_code="SECURITY_ERROR",
            details=error_details,
        )


class WebScrapingError(MealPlannerException):
    """Raised when web scraping fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        http_status: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize web scraping error.

        Args:
            message: Error description
            url: URL that failed
            http_status: HTTP status code
            timeout_seconds: Timeout that was exceeded
            details: Additional context
        """
        error_details = details or {}
        if url:
            error_details["url"] = url
        if http_status:
            error_details["http_status"] = http_status
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds

        super().__init__(
            message=message,
            error_code="WEB_SCRAPING_ERROR",
            details=error_details,
        )


class ConfigurationError(MealPlannerException):
    """Raised when configuration is invalid."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize configuration error.

        Args:
            message: Error description
            config_key: Configuration key that's invalid
            config_value: Configuration value that's invalid
            details: Additional context
        """
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
        if config_value:
            error_details["config_value"] = config_value

        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=error_details,
        )


class AgentError(MealPlannerException):
    """Raised when an AI agent encounters an error."""

    def __init__(
        self,
        message: str,
        agent_name: Optional[str] = None,
        agent_task: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize agent error.

        Args:
            message: Error description
            agent_name: Name of the agent that failed
            agent_task: Task the agent was performing
            details: Additional context
        """
        error_details = details or {}
        if agent_name:
            error_details["agent_name"] = agent_name
        if agent_task:
            error_details["agent_task"] = agent_task

        super().__init__(
            message=message,
            error_code="AGENT_ERROR",
            details=error_details,
        )


# Exception handlers and utilities

def format_error_response(exception: MealPlannerException, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Format exception as standardized error response.

    Args:
        exception: The exception to format
        request_id: Optional request ID for tracking

    Returns:
        Formatted error response dictionary
    """
    response = exception.to_dict()
    if request_id:
        response["request_id"] = request_id

    return response


def is_retryable_error(exception: MealPlannerException) -> bool:
    """
    Determine if an error is retryable.

    Args:
        exception: Exception to check

    Returns:
        True if the error suggests retry might succeed
    """
    retryable_codes = {
        "WEB_SCRAPING_ERROR",  # Network issues might be temporary
        "RECIPE_PARSING_ERROR",  # Might work with different extraction method
    }

    # Check for specific conditions that suggest retry
    if exception.error_code in retryable_codes:
        # Don't retry security errors or 4xx HTTP errors
        if "security_check" in exception.details:
            return False

        http_status = exception.details.get("http_status")
        if http_status and 400 <= http_status < 500:
            return False

        return True

    return False