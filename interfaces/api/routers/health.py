"""
Health check router for Holiday Meal Planner API.

Provides health check endpoints for monitoring service status and dependencies.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from datetime import datetime

from interfaces.api.dependencies import validated_context, is_health_check_endpoint
from interfaces.api.responses import HealthCheckResponse
from shared.config import get_settings


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health Check"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check service health and dependency status",
    include_in_schema=True
)
async def health_check(
    context: Annotated[dict, validated_context()]
) -> HealthCheckResponse:
    """
    Comprehensive health check for the service.

    Returns health status of the service and its dependencies.
    Used for monitoring, load balancer health checks, and debugging.

    Args:
        context: Request context for logging

    Returns:
        Health check response with status and dependency information
    """
    try:
        logger.debug("Performing health check")

        # Check service dependencies
        dependencies = await _check_dependencies()

        # Determine overall status
        overall_status = "healthy"
        for dep_status in dependencies.values():
            if dep_status not in ["operational", "healthy"]:
                overall_status = "degraded"
                break

        response = HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version="1.0.0",
            dependencies=dependencies
        )

        if overall_status != "healthy":
            logger.warning(f"Health check shows degraded status: {dependencies}")
        else:
            logger.debug("Health check completed successfully")

        return response

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)

        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            dependencies={"error": str(e)}
        )


@router.get(
    "/ping",
    summary="Simple ping",
    description="Simple ping endpoint for basic availability checks",
    include_in_schema=True
)
async def ping() -> dict:
    """
    Simple ping endpoint for basic availability checks.

    Lightweight endpoint that returns immediately to confirm
    the service is responding to requests.

    Returns:
        Simple ping response
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Holiday Meal Planner API is running"
    }


@router.get(
    "/readiness",
    summary="Readiness check",
    description="Check if service is ready to handle requests",
    include_in_schema=True
)
async def readiness_check() -> dict:
    """
    Kubernetes-style readiness check.

    Indicates whether the service is ready to handle requests.
    Used by Kubernetes and other orchestrators to determine
    when to start sending traffic to a pod.

    Returns:
        Readiness status
    """
    try:
        # Check critical dependencies
        dependencies = await _check_critical_dependencies()

        # Check if any critical dependency is down
        critical_issues = [
            dep for dep, status in dependencies.items()
            if status in ["unavailable", "error", "timeout"]
        ]

        if critical_issues:
            logger.warning(f"Readiness check failed - critical issues: {critical_issues}")
            return {
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Critical dependencies unavailable: {critical_issues}",
                "dependencies": dependencies
            }

        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Service is ready to handle requests",
            "dependencies": dependencies
        }

    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        return {
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Readiness check failed",
            "error": str(e)
        }


@router.get(
    "/liveness",
    summary="Liveness check",
    description="Check if service is alive and should not be restarted",
    include_in_schema=True
)
async def liveness_check() -> dict:
    """
    Kubernetes-style liveness check.

    Indicates whether the service is alive and functioning.
    Used by Kubernetes to determine if a pod should be restarted.

    Returns:
        Liveness status
    """
    try:
        # Basic liveness check - service is alive if it can respond
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Service is alive and functioning"
        }

    except Exception as e:
        logger.error(f"Liveness check failed: {e}", exc_info=True)
        return {
            "status": "dead",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Liveness check failed",
            "error": str(e)
        }


async def _check_dependencies() -> dict:
    """
    Check status of all service dependencies.

    Returns:
        Dictionary mapping dependency names to status strings
    """
    dependencies = {}

    try:
        # Check web scraping capability
        dependencies["web_scraping"] = await _check_web_scraping()

        # Check NLP processing
        dependencies["nlp_processing"] = await _check_nlp_processing()

        # Check timeline generation
        dependencies["timeline_generation"] = await _check_timeline_generation()

        # Check configuration
        dependencies["configuration"] = _check_configuration()

        # Check memory usage (basic check)
        dependencies["memory"] = _check_memory_usage()

    except Exception as e:
        logger.error(f"Error checking dependencies: {e}")
        dependencies["dependency_check"] = f"error: {e}"

    return dependencies


async def _check_critical_dependencies() -> dict:
    """
    Check status of critical dependencies only.

    Returns:
        Dictionary mapping critical dependency names to status strings
    """
    critical_deps = {}

    try:
        # Only check dependencies that are critical for basic operation
        critical_deps["configuration"] = _check_configuration()
        critical_deps["memory"] = _check_memory_usage()

    except Exception as e:
        logger.error(f"Error checking critical dependencies: {e}")
        critical_deps["critical_check"] = f"error: {e}"

    return critical_deps


async def _check_web_scraping() -> str:
    """Check web scraping service availability."""
    try:
        # Import here to avoid circular dependencies
        from shared.validators import validate_url_security

        # Test URL validation (basic smoke test)
        test_url = "https://example.com/test"
        validate_url_security(test_url)

        return "operational"

    except Exception as e:
        logger.warning(f"Web scraping check failed: {e}")
        return "degraded"


async def _check_nlp_processing() -> str:
    """Check NLP processing service availability."""
    try:
        # Test basic NLP imports and functionality
        import spacy

        # Check if we can access core NLP modules
        from core.services import nlp_processor

        return "operational"

    except ImportError as e:
        logger.warning(f"NLP processing unavailable - missing dependencies: {e}")
        return "unavailable"
    except Exception as e:
        logger.warning(f"NLP processing check failed: {e}")
        return "degraded"


async def _check_timeline_generation() -> str:
    """Check timeline generation service availability."""
    try:
        # Test timeline generation imports
        import networkx as nx
        from core.services.scheduler import TaskDependencyAnalyzer
        from core.agents.timeline_generator import TimelineGeneratorAgent

        return "operational"

    except ImportError as e:
        logger.warning(f"Timeline generation unavailable - missing dependencies: {e}")
        return "unavailable"
    except Exception as e:
        logger.warning(f"Timeline generation check failed: {e}")
        return "degraded"


def _check_configuration() -> str:
    """Check configuration loading and validity."""
    try:
        settings = get_settings()

        # Verify critical settings are present
        if not hasattr(settings, 'web_request_timeout'):
            return "misconfigured"

        if settings.web_request_timeout <= 0:
            return "invalid"

        return "operational"

    except Exception as e:
        logger.warning(f"Configuration check failed: {e}")
        return "error"


def _check_memory_usage() -> str:
    """Check basic memory usage indicators."""
    try:
        import psutil
        import os

        # Get current process memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        # Simple threshold check (adjust based on your requirements)
        if memory_mb > 1000:  # 1GB threshold
            logger.warning(f"High memory usage: {memory_mb:.1f}MB")
            return "high_usage"
        elif memory_mb > 500:  # 500MB threshold
            return "moderate_usage"
        else:
            return "normal"

    except ImportError:
        # psutil not available, skip memory check
        return "unavailable"
    except Exception as e:
        logger.warning(f"Memory check failed: {e}")
        return "error"