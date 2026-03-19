"""
Shared dependencies for Holiday Meal Planner API.

Provides rate limiting, input validation, error handling,
and common dependency injection for FastAPI endpoints.
"""

import asyncio
import time
from typing import Optional, Dict, Any, Annotated
from datetime import datetime, timedelta
from collections import defaultdict, deque

from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ValidationError
import logging

from shared.config import get_settings
from shared.exceptions import MealPlannerException
from interfaces.api.responses import ErrorDetailResponse, ValidationErrorResponse


logger = logging.getLogger(__name__)

# Global rate limiter storage (in production, use Redis or similar)
_rate_limit_storage: Dict[str, deque] = defaultdict(deque)
_rate_limit_lock = asyncio.Lock()


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    max_requests: int = 100
    window_minutes: int = 60
    burst_allowance: int = 10


class ValidationConfig(BaseModel):
    """Input validation configuration."""
    max_menu_items: int = 20
    max_url_length: int = 2048
    max_description_length: int = 500
    max_prep_days: int = 14
    max_daily_hours: int = 12


# Configuration instances
rate_limit_config = RateLimitConfig()
validation_config = ValidationConfig()

# Security scheme (placeholder for future authentication)
security = HTTPBearer(auto_error=False)


async def check_rate_limit(
    request: Request,
    config: RateLimitConfig = rate_limit_config
) -> None:
    """
    Check if request is within rate limits.

    Args:
        request: FastAPI request object
        config: Rate limiting configuration

    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = request.client.host
    current_time = time.time()
    window_start = current_time - (config.window_minutes * 60)

    async with _rate_limit_lock:
        # Get or create request history for this IP
        request_history = _rate_limit_storage[client_ip]

        # Remove old requests outside the window
        while request_history and request_history[0] < window_start:
            request_history.popleft()

        # Check if limit exceeded
        if len(request_history) >= config.max_requests:
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error_type": "RateLimitError",
                    "message": f"Rate limit exceeded. Maximum {config.max_requests} requests per {config.window_minutes} minutes.",
                    "retry_after": int(config.window_minutes * 60 - (current_time - request_history[0])) if request_history else config.window_minutes * 60
                }
            )

        # Add current request to history
        request_history.append(current_time)


async def validate_menu_request(
    menu_items: list,
    config: ValidationConfig = validation_config
) -> None:
    """
    Validate menu processing request.

    Args:
        menu_items: List of menu items to validate
        config: Validation configuration

    Raises:
        HTTPException: If validation fails
    """
    validation_errors = []

    # Check number of menu items
    if len(menu_items) == 0:
        validation_errors.append({
            "field": "menu_items",
            "message": "At least one menu item is required",
            "input": len(menu_items)
        })
    elif len(menu_items) > config.max_menu_items:
        validation_errors.append({
            "field": "menu_items",
            "message": f"Maximum {config.max_menu_items} menu items allowed",
            "input": len(menu_items)
        })

    # Validate individual menu items
    for i, item in enumerate(menu_items):
        # Check that either source_url or description is provided
        if not item.get('source_url') and not item.get('description'):
            validation_errors.append({
                "field": f"menu_items[{i}]",
                "message": "Either source_url or description must be provided",
                "input": item
            })

        # Validate URL length
        if item.get('source_url') and len(str(item['source_url'])) > config.max_url_length:
            validation_errors.append({
                "field": f"menu_items[{i}].source_url",
                "message": f"URL length exceeds {config.max_url_length} characters",
                "input": len(str(item['source_url']))
            })

        # Validate description length
        if item.get('description') and len(item['description']) > config.max_description_length:
            validation_errors.append({
                "field": f"menu_items[{i}].description",
                "message": f"Description length exceeds {config.max_description_length} characters",
                "input": len(item['description'])
            })

        # Validate serving size
        serving_size = item.get('serving_size', 1)
        if not isinstance(serving_size, int) or serving_size < 1 or serving_size > 100:
            validation_errors.append({
                "field": f"menu_items[{i}].serving_size",
                "message": "Serving size must be between 1 and 100",
                "input": serving_size
            })

    if validation_errors:
        error_response = ValidationErrorResponse(
            error=ErrorDetailResponse(
                error_type="ValidationError",
                message="Request validation failed",
                error_code="VAL_001"
            ),
            validation_errors=validation_errors
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_response.dict()
        )


async def validate_meal_datetime(meal_datetime: Optional[datetime]) -> Optional[datetime]:
    """
    Validate meal datetime parameter.

    Args:
        meal_datetime: Meal date and time to validate

    Returns:
        Validated datetime or None if not provided

    Raises:
        HTTPException: If datetime is invalid
    """
    if meal_datetime is None:
        return None

    # Check if date is in the future
    if meal_datetime <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "ValidationError",
                "message": "Meal date must be in the future",
                "details": {"meal_datetime": meal_datetime.isoformat()},
                "suggestion": "Provide a future date and time"
            }
        )

    # Check if date is not too far in the future (1 year max)
    max_future_date = datetime.utcnow() + timedelta(days=365)
    if meal_datetime > max_future_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "ValidationError",
                "message": "Meal date cannot be more than 1 year in the future",
                "details": {"meal_datetime": meal_datetime.isoformat()},
                "suggestion": "Choose a date within the next year"
            }
        )

    return meal_datetime


async def validate_timeline_params(
    max_prep_days: Optional[int] = None,
    max_daily_hours: Optional[int] = None,
    config: ValidationConfig = validation_config
) -> tuple[int, int]:
    """
    Validate timeline generation parameters.

    Args:
        max_prep_days: Maximum preparation days
        max_daily_hours: Maximum daily hours
        config: Validation configuration

    Returns:
        Tuple of validated (max_prep_days, max_daily_hours)

    Raises:
        HTTPException: If parameters are invalid
    """
    validated_prep_days = max_prep_days or 7
    validated_daily_hours = max_daily_hours or 4

    if validated_prep_days < 1 or validated_prep_days > config.max_prep_days:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "ValidationError",
                "message": f"max_prep_days must be between 1 and {config.max_prep_days}",
                "details": {"max_prep_days": validated_prep_days}
            }
        )

    if validated_daily_hours < 1 or validated_daily_hours > config.max_daily_hours:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_type": "ValidationError",
                "message": f"max_daily_hours must be between 1 and {config.max_daily_hours}",
                "details": {"max_daily_hours": validated_daily_hours}
            }
        )

    return validated_prep_days, validated_daily_hours


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> Optional[Dict[str, Any]]:
    """
    Get current user from authorization header (placeholder).

    Args:
        credentials: HTTP authorization credentials

    Returns:
        User information or None for anonymous access

    Note:
        This is a placeholder for future authentication implementation.
        Currently allows anonymous access to all endpoints.
    """
    if credentials:
        # In a real implementation, validate the token here
        # For now, we'll just return a placeholder user
        return {
            "user_id": "anonymous",
            "tier": "free",
            "rate_limit_multiplier": 1.0
        }

    return None


async def get_request_context(
    request: Request,
    user: Annotated[Optional[Dict[str, Any]], Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Build request context for logging and monitoring.

    Args:
        request: FastAPI request object
        user: Current user information

    Returns:
        Request context dictionary
    """
    return {
        "request_id": getattr(request.state, "request_id", None),
        "client_ip": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "user": user,
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint": f"{request.method} {request.url.path}",
        "query_params": dict(request.query_params)
    }


class APIErrorHandler:
    """Handler for converting application exceptions to HTTP responses."""

    @staticmethod
    def handle_meal_planner_exception(exc: MealPlannerException) -> HTTPException:
        """Convert MealPlannerException to HTTP error."""
        error_mapping = {
            "SecurityError": status.HTTP_400_BAD_REQUEST,
            "WebScrapingError": status.HTTP_502_BAD_GATEWAY,
            "RecipeParsingError": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "IngredientConsolidationError": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "TimelineGenerationError": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "AgentError": status.HTTP_500_INTERNAL_SERVER_ERROR
        }

        error_type = type(exc).__name__
        status_code = error_mapping.get(error_type, status.HTTP_500_INTERNAL_SERVER_ERROR)

        suggestions = {
            "SecurityError": "Ensure URLs use HTTPS and are from trusted sources",
            "WebScrapingError": "Try a different recipe URL or use a description instead",
            "RecipeParsingError": "Provide a clearer recipe description or different URL",
            "IngredientConsolidationError": "Try reducing similarity threshold",
            "TimelineGenerationError": "Simplify the menu or increase preparation time limits"
        }

        return HTTPException(
            status_code=status_code,
            detail={
                "error_type": error_type,
                "message": str(exc),
                "suggestion": suggestions.get(error_type),
                "error_code": getattr(exc, 'error_code', None)
            }
        )

    @staticmethod
    def handle_validation_error(exc: ValidationError) -> HTTPException:
        """Convert Pydantic validation error to HTTP error."""
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": ".".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })

        error_response = ValidationErrorResponse(
            error=ErrorDetailResponse(
                error_type="ValidationError",
                message="Request validation failed",
                error_code="VAL_002"
            ),
            validation_errors=validation_errors
        )

        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_response.dict()
        )

    @staticmethod
    def handle_generic_exception(exc: Exception) -> HTTPException:
        """Convert generic exception to HTTP error."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "InternalServerError",
                "message": "An internal server error occurred",
                "error_code": "INT_001"
            }
        )


# Dependency functions for FastAPI
def rate_limited():
    """Rate limiting dependency."""
    return Depends(check_rate_limit)

def validated_context():
    """Request context dependency."""
    return Depends(get_request_context)

def authenticated_user():
    """User authentication dependency."""
    return Depends(get_current_user)


# Middleware helper functions
def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies."""
    # Check for forwarded IP headers
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Use the first IP in the chain
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    return request.client.host


def is_health_check_endpoint(request: Request) -> bool:
    """Check if request is for health check endpoint."""
    return request.url.path in ["/health", "/v1/health", "/ping"]