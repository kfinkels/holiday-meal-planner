"""
Input validation utilities for Holiday Meal Planner.

Provides comprehensive validation for URLs, text inputs, and data sanitization
with security-first approach.
"""

import re
import html
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urlparse, parse_qs
from pydantic import BaseModel, validator, Field

from .config import get_settings
from .exceptions import ValidationError, SecurityError


class URLValidationResult(BaseModel):
    """Result of URL validation with details."""

    is_valid: bool = Field(..., description="Whether URL is valid")
    url: str = Field(..., description="Original URL")
    normalized_url: Optional[str] = Field(None, description="Normalized URL if valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")


class TextValidationResult(BaseModel):
    """Result of text validation with sanitized content."""

    is_valid: bool = Field(..., description="Whether text is valid")
    original_text: str = Field(..., description="Original text")
    sanitized_text: Optional[str] = Field(None, description="Sanitized text if valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")


# URL Validation

def validate_recipe_url(url: str, strict: bool = True) -> URLValidationResult:
    """
    Validate and normalize a recipe URL.

    Args:
        url: URL to validate
        strict: Whether to apply strict validation rules

    Returns:
        URLValidationResult with validation details
    """
    result = URLValidationResult(is_valid=False, url=url)
    settings = get_settings()

    try:
        # Basic URL parsing
        if not url or not isinstance(url, str):
            result.errors.append("URL must be a non-empty string")
            return result

        # Strip whitespace and normalize
        normalized_url = url.strip()

        # Check for basic URL structure
        if not normalized_url.startswith(("http://", "https://")):
            if strict:
                result.errors.append("URL must start with http:// or https://")
                return result
            else:
                # Try to add https://
                normalized_url = f"https://{normalized_url}"
                result.warnings.append("Added https:// prefix to URL")

        # Parse URL components
        try:
            parsed = urlparse(normalized_url)
        except Exception as e:
            result.errors.append(f"Invalid URL format: {e}")
            return result

        # Validate URL components
        if not parsed.hostname:
            result.errors.append("URL must have a valid hostname")
            return result

        if not parsed.scheme:
            result.errors.append("URL must have a valid scheme")
            return result

        # HTTPS-only check
        if settings.https_only and parsed.scheme != "https":
            result.errors.append("Only HTTPS URLs are allowed")
            return result

        # Security checks - additional validation
        security_warnings = check_input_security(normalized_url)
        if security_warnings:
            result.errors.extend([f"Security issue: {warning}" for warning in security_warnings])
            return result

        # Check for suspicious patterns
        suspicious_patterns = [
            r"javascript:",
            r"data:",
            r"file:",
            r"ftp:",
            r"<script",
            r"onclick=",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, normalized_url, re.IGNORECASE):
                result.errors.append(f"URL contains suspicious pattern: {pattern}")
                return result

        # Validate hostname is not an IP address (basic check)
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", parsed.hostname):
            if strict:
                result.errors.append("IP addresses are not allowed")
                return result
            else:
                result.warnings.append("Using IP address instead of domain name")

        # Check for reasonable URL length
        if len(normalized_url) > 2048:
            result.errors.append("URL is too long (max 2048 characters)")
            return result

        # Validate TLD (basic check for common recipe sites)
        common_recipe_tlds = {".com", ".org", ".net", ".edu", ".co", ".uk", ".ca"}
        if strict and not any(parsed.hostname.endswith(tld) for tld in common_recipe_tlds):
            result.warnings.append("URL uses uncommon TLD for recipe sites")

        # All checks passed
        result.is_valid = True
        result.normalized_url = normalized_url

    except Exception as e:
        result.errors.append(f"Unexpected validation error: {e}")

    return result


def validate_recipe_urls(urls: List[str], strict: bool = True) -> List[URLValidationResult]:
    """
    Validate multiple recipe URLs.

    Args:
        urls: List of URLs to validate
        strict: Whether to apply strict validation rules

    Returns:
        List of URLValidationResult objects
    """
    return [validate_recipe_url(url, strict) for url in urls]


# Text Validation and Sanitization

def sanitize_dish_description(text: str, max_length: int = 500) -> TextValidationResult:
    """
    Sanitize and validate dish description text.

    Args:
        text: Text to sanitize
        max_length: Maximum allowed length

    Returns:
        TextValidationResult with sanitized text
    """
    result = TextValidationResult(is_valid=False, original_text=text)

    try:
        # Basic validation
        if not text or not isinstance(text, str):
            result.errors.append("Description must be a non-empty string")
            return result

        # HTML entity decoding and escaping
        sanitized = html.unescape(text)
        sanitized = html.escape(sanitized, quote=False)

        # Strip dangerous characters
        sanitized = re.sub(r'[<>"\']', "", sanitized)

        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        # Length validation
        if len(sanitized) < 10:
            result.errors.append("Description too short (minimum 10 characters)")
            return result

        if len(sanitized) > max_length:
            result.errors.append(f"Description too long (maximum {max_length} characters)")
            return result

        # Content validation - should contain food-related terms
        food_indicators = [
            r'\b(recipe|dish|meal|food|cook|bake|roast|grill|fry|steam)\b',
            r'\b(chicken|beef|pork|fish|turkey|vegetable|potato|rice)\b',
            r'\b(sauce|soup|salad|bread|cake|pie|pasta|cheese)\b',
            r'\b(for \d+ people|serves \d+|serving|portion)\b',
        ]

        has_food_context = any(
            re.search(pattern, sanitized.lower()) for pattern in food_indicators
        )

        if not has_food_context:
            result.warnings.append("Description may not contain food-related content")

        # Check for script-like content
        script_patterns = [
            r'function\s*\(',
            r'var\s+\w+',
            r'document\.',
            r'window\.',
            r'eval\s*\(',
        ]

        for pattern in script_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                result.errors.append("Description contains script-like content")
                return result

        # All checks passed
        result.is_valid = True
        result.sanitized_text = sanitized

    except Exception as e:
        result.errors.append(f"Unexpected sanitization error: {e}")

    return result


# Ingredient Name Validation

def validate_ingredient_name(name: str) -> bool:
    """
    Validate ingredient name for safety and reasonableness.

    Args:
        name: Ingredient name to validate

    Returns:
        True if name is valid
    """
    if not name or not isinstance(name, str):
        return False

    # Length check
    if len(name.strip()) < 1 or len(name) > 100:
        return False

    # Character validation - allow letters, numbers, spaces, and common punctuation
    if not re.match(r'^[a-zA-Z0-9\s\-\.\,\(\)\/&]+$', name):
        return False

    # Not just numbers or symbols
    if re.match(r'^[\d\s\-\.\,\(\)\/&]+$', name):
        return False

    return True


# Numeric Validation

def validate_serving_size(serving_size: Union[int, str], min_size: int = 1, max_size: int = 100) -> int:
    """
    Validate and normalize serving size.

    Args:
        serving_size: Serving size to validate
        min_size: Minimum allowed size
        max_size: Maximum allowed size

    Returns:
        Validated serving size as integer

    Raises:
        ValidationError: If serving size is invalid
    """
    try:
        # Convert to int if string
        if isinstance(serving_size, str):
            serving_size = int(serving_size)

        if not isinstance(serving_size, int):
            raise ValidationError("Serving size must be an integer")

        if serving_size < min_size or serving_size > max_size:
            raise ValidationError(
                f"Serving size must be between {min_size} and {max_size}",
                field_name="serving_size",
                invalid_value=serving_size,
            )

        return serving_size

    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"Invalid serving size: {e}",
            field_name="serving_size",
            invalid_value=serving_size,
        )


def validate_confidence_score(score: Union[float, str], min_score: float = 0.0, max_score: float = 1.0) -> float:
    """
    Validate confidence score.

    Args:
        score: Confidence score to validate
        min_score: Minimum allowed score
        max_score: Maximum allowed score

    Returns:
        Validated confidence score

    Raises:
        ValidationError: If score is invalid
    """
    try:
        if isinstance(score, str):
            score = float(score)

        if not isinstance(score, (int, float)):
            raise ValidationError("Confidence score must be a number")

        if score < min_score or score > max_score:
            raise ValidationError(
                f"Confidence score must be between {min_score} and {max_score}",
                field_name="confidence",
                invalid_value=score,
            )

        return float(score)

    except (ValueError, TypeError) as e:
        raise ValidationError(
            f"Invalid confidence score: {e}",
            field_name="confidence",
            invalid_value=score,
        )


# Request Validation

def validate_menu_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize menu processing request.

    Args:
        request_data: Raw request data

    Returns:
        Validated and sanitized request data

    Raises:
        ValidationError: If request is invalid
    """
    settings = get_settings()
    validated = {}

    # Validate menu_items
    menu_items = request_data.get("menu_items", [])
    if not isinstance(menu_items, list):
        raise ValidationError("menu_items must be a list")

    if len(menu_items) == 0:
        raise ValidationError("At least one menu item is required")

    if len(menu_items) > settings.max_menu_items:
        raise ValidationError(
            f"Too many menu items (max {settings.max_menu_items})",
            field_name="menu_items",
            invalid_value=len(menu_items),
        )

    validated_items = []
    for i, item in enumerate(menu_items):
        if not isinstance(item, dict):
            raise ValidationError(f"Menu item {i} must be an object")

        validated_item = {}

        # Validate URL if present
        if "source_url" in item:
            url_result = validate_recipe_url(item["source_url"])
            if not url_result.is_valid:
                raise ValidationError(
                    f"Invalid URL in menu item {i}: {'; '.join(url_result.errors)}",
                    field_name=f"menu_items[{i}].source_url",
                    invalid_value=item["source_url"],
                )
            validated_item["source_url"] = url_result.normalized_url

        # Validate description if present
        if "description" in item:
            text_result = sanitize_dish_description(item["description"])
            if not text_result.is_valid:
                raise ValidationError(
                    f"Invalid description in menu item {i}: {'; '.join(text_result.errors)}",
                    field_name=f"menu_items[{i}].description",
                    invalid_value=item["description"],
                )
            validated_item["description"] = text_result.sanitized_text

        # Must have either URL or description
        if "source_url" not in validated_item and "description" not in validated_item:
            raise ValidationError(
                f"Menu item {i} must have either source_url or description"
            )

        # Validate serving_size
        serving_size = item.get("serving_size", 8)
        validated_item["serving_size"] = validate_serving_size(serving_size)

        validated_items.append(validated_item)

    validated["menu_items"] = validated_items

    # Validate other optional fields
    if "meal_datetime" in request_data:
        # Basic datetime validation - will be handled by Pydantic models
        validated["meal_datetime"] = request_data["meal_datetime"]

    if "max_prep_days" in request_data:
        max_prep_days = request_data["max_prep_days"]
        if not isinstance(max_prep_days, int) or max_prep_days < 1 or max_prep_days > settings.max_prep_days:
            raise ValidationError(
                f"max_prep_days must be between 1 and {settings.max_prep_days}",
                field_name="max_prep_days",
                invalid_value=max_prep_days,
            )
        validated["max_prep_days"] = max_prep_days

    if "max_daily_hours" in request_data:
        max_daily_hours = request_data["max_daily_hours"]
        if not isinstance(max_daily_hours, (int, float)) or max_daily_hours < 1 or max_daily_hours > settings.max_daily_prep_hours:
            raise ValidationError(
                f"max_daily_hours must be between 1 and {settings.max_daily_prep_hours}",
                field_name="max_daily_hours",
                invalid_value=max_daily_hours,
            )
        validated["max_daily_hours"] = float(max_daily_hours)

    return validated


# Security utilities

def check_input_security(text: str) -> List[str]:
    """
    Check text input for security issues.

    Args:
        text: Text to check

    Returns:
        List of security warnings (empty if safe)
    """
    warnings = []

    # Check for script injection patterns
    script_patterns = [
        (r'<script.*?>.*?</script>', "Script tag detected"),
        (r'javascript:', "JavaScript protocol detected"),
        (r'on\w+\s*=', "Event handler detected"),
        (r'eval\s*\(', "Eval function detected"),
        (r'document\.\w+', "DOM access detected"),
        (r'window\.\w+', "Window object access detected"),
    ]

    for pattern, message in script_patterns:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            warnings.append(message)

    # Check for SQL injection patterns
    sql_patterns = [
        (r'\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(from|where|into)\b', "SQL keywords detected"),
        (r"['\"][^'\"]*['\"].*--", "SQL comment detected"),
        (r"\b(or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+['\"]?", "SQL boolean logic detected"),
    ]

    for pattern, message in sql_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(message)

    return warnings


def validate_url_security(url: str, raise_on_fail: bool = True) -> bool:
    """
    Validate URL for security compliance.

    Args:
        url: URL to validate
        raise_on_fail: Whether to raise exception on security failure

    Returns:
        True if URL is secure

    Raises:
        SecurityError: If URL fails security validation and raise_on_fail is True
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)

    # Check for HTTPS
    if parsed.scheme != 'https':
        if raise_on_fail:
            raise SecurityError("Only HTTPS URLs are allowed", url=url)
        return False

    # Check for blocked domains or IP addresses
    if parsed.hostname:
        # Block localhost and private IP ranges
        blocked_hosts = ['localhost', '127.0.0.1', '0.0.0.0']
        if parsed.hostname in blocked_hosts:
            if raise_on_fail:
                raise SecurityError("Localhost URLs are not allowed", url=url)
            return False

        # Block private IP ranges (basic check)
        import re
        if re.match(r'^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)', parsed.hostname):
            if raise_on_fail:
                raise SecurityError("Private IP addresses are not allowed", url=url)
            return False

    # Check for suspicious patterns
    security_warnings = check_input_security(url)
    if security_warnings:
        if raise_on_fail:
            raise SecurityError(f"Security issues detected: {', '.join(security_warnings)}", url=url)
        return False

    return True