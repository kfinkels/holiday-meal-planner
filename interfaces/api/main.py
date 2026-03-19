"""
FastAPI application for Holiday Meal Planner API.

Main application setup with router registration, CORS configuration,
middleware, error handling, and OpenAPI documentation.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from pydantic import ValidationError
import uvicorn

from interfaces.api.routers import process_router, jobs_router, health_router
from interfaces.api.dependencies import APIErrorHandler, get_client_ip
from shared.config import get_settings
from shared.exceptions import MealPlannerException


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("🍽️  Holiday Meal Planner API starting up...")

    # Initialize any required services here
    settings = get_settings()
    logger.info(f"Configuration loaded: {settings}")

    # Log startup completion
    logger.info("✅ Holiday Meal Planner API startup completed")

    yield

    # Shutdown
    logger.info("🔄 Holiday Meal Planner API shutting down...")
    # Cleanup resources here if needed
    logger.info("✅ Holiday Meal Planner API shutdown completed")


# Create FastAPI application
def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="Holiday Meal Planner API",
        description="""
        🍽️ **Holiday Meal Planner API**

        AI-powered holiday meal planning service that processes recipes and generates
        consolidated grocery lists with day-by-day preparation timelines.

        ## Features

        - **Recipe Processing**: Extract ingredients from URLs or descriptions
        - **Grocery List Generation**: Consolidate ingredients with smart deduplication
        - **Timeline Planning**: Create optimized day-by-day preparation schedules
        - **Multiple Interfaces**: Both synchronous and asynchronous processing
        - **Security First**: HTTPS-only URLs, input validation, rate limiting

        ## Authentication

        Currently supports anonymous access. Authentication may be added in future versions.

        ## Rate Limiting

        - **Free tier**: 100 requests per hour
        - **Burst allowance**: Up to 10 requests in quick succession

        ## Support

        For questions or issues, visit our [GitHub repository](https://github.com/your-org/holiday-meal-planner).
        """,
        version="1.0.0",
        contact={
            "name": "Holiday Meal Planner Team",
            "url": "https://github.com/your-org/holiday-meal-planner",
            "email": "support@holiday-meal-planner.com"
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        },
        servers=[
            {
                "url": "https://api.holiday-meal-planner.com/v1",
                "description": "Production server"
            },
            {
                "url": "http://localhost:8000/v1",
                "description": "Local development server"
            }
        ],
        lifespan=lifespan,
        docs_url="/docs",  # Swagger UI
        redoc_url="/redoc",  # ReDoc
        openapi_url="/openapi.json"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://holiday-meal-planner.com",
            "https://www.holiday-meal-planner.com",
            "http://localhost:3000",  # React dev server
            "http://localhost:8080",  # Vue dev server
            "http://127.0.0.1:8000",  # Local API testing
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Request-ID"
        ],
        expose_headers=["X-Request-ID", "X-Processing-Time"]
    )

    # Add trusted host middleware for security
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "api.holiday-meal-planner.com",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",  # For Docker containers
        ]
    )

    # Add custom middleware
    add_request_middleware(app)

    # Register routers
    register_routers(app)

    # Add exception handlers
    add_exception_handlers(app)

    # Customize OpenAPI schema
    customize_openapi(app)

    return app


def add_request_middleware(app: FastAPI) -> None:
    """
    Add custom request middleware for logging and monitoring.

    Args:
        app: FastAPI application instance
    """

    @app.middleware("http")
    async def request_middleware(request: Request, call_next: Callable):
        """Request processing middleware."""
        start_time = time.time()

        # Generate request ID
        request_id = str(uuid4())
        request.state.request_id = request_id

        # Log request start
        client_ip = get_client_ip(request)
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"[{request_id}] from {client_ip}"
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time
            processing_time_ms = round(process_time * 1000, 2)

            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processing-Time"] = f"{processing_time_ms}ms"

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"[{request_id}] {response.status_code} in {processing_time_ms}ms"
            )

            return response

        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            processing_time_ms = round(process_time * 1000, 2)

            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"[{request_id}] error: {str(e)} in {processing_time_ms}ms",
                exc_info=True
            )

            # Re-raise to let exception handlers deal with it
            raise


def register_routers(app: FastAPI) -> None:
    """
    Register all API routers.

    Args:
        app: FastAPI application instance
    """
    # API version prefix
    API_PREFIX = "/v1"

    # Register routers with prefix
    app.include_router(
        process_router,
        prefix=API_PREFIX,
        dependencies=[]
    )

    app.include_router(
        jobs_router,
        prefix=API_PREFIX,
        dependencies=[]
    )

    app.include_router(
        health_router,
        prefix="",  # Health endpoints at root level
        dependencies=[]
    )

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """
        API root endpoint.

        Returns basic API information and links to documentation.
        """
        return {
            "name": "Holiday Meal Planner API",
            "version": "1.0.0",
            "description": "AI-powered holiday meal planning and grocery list generation",
            "documentation": {
                "swagger": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json"
            },
            "endpoints": {
                "process_menu": "/v1/process",
                "async_processing": "/v1/process/async",
                "job_status": "/v1/jobs/{job_id}",
                "health_check": "/health"
            },
            "support": {
                "github": "https://github.com/your-org/holiday-meal-planner",
                "documentation": "https://holiday-meal-planner.readthedocs.io/"
            }
        }


def add_exception_handlers(app: FastAPI) -> None:
    """
    Add global exception handlers.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.warning(
            f"HTTP exception: {exc.status_code} {exc.detail} "
            f"[{request_id}] {request.method} {request.url.path}"
        )

        # Ensure detail is properly formatted
        detail = exc.detail
        if isinstance(detail, str):
            detail = {
                "error_type": "HTTPException",
                "message": detail
            }

        return JSONResponse(
            status_code=exc.status_code,
            content=detail,
            headers={"X-Request-ID": request_id}
        )

    @app.exception_handler(MealPlannerException)
    async def meal_planner_exception_handler(request: Request, exc: MealPlannerException):
        """Handle application-specific exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.error(
            f"Meal planner exception: {exc} "
            f"[{request_id}] {request.method} {request.url.path}"
        )

        http_exc = APIErrorHandler.handle_meal_planner_exception(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
            headers={"X-Request-ID": request_id}
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.warning(
            f"Validation exception: {exc} "
            f"[{request_id}] {request.method} {request.url.path}"
        )

        http_exc = APIErrorHandler.handle_validation_error(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
            headers={"X-Request-ID": request_id}
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.error(
            f"Unexpected exception: {exc} "
            f"[{request_id}] {request.method} {request.url.path}",
            exc_info=True
        )

        http_exc = APIErrorHandler.handle_generic_exception(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
            headers={"X-Request-ID": request_id}
        )


def customize_openapi(app: FastAPI) -> None:
    """
    Customize OpenAPI schema generation.

    Args:
        app: FastAPI application instance
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            servers=app.servers
        )

        # Add custom schema modifications
        openapi_schema["info"]["x-logo"] = {
            "url": "https://holiday-meal-planner.com/logo.png"
        }

        # Add security schemes (for future authentication)
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT Bearer token authentication (future feature)"
            }
        }

        # Add common response schemas
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}

        openapi_schema["components"]["responses"] = {
            "BadRequest": {
                "description": "Bad Request",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ErrorDetailResponse"
                        }
                    }
                }
            },
            "ValidationError": {
                "description": "Validation Error",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ValidationErrorResponse"
                        }
                    }
                }
            },
            "InternalError": {
                "description": "Internal Server Error",
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/ErrorDetailResponse"
                        }
                    }
                }
            }
        }

        # Add tags metadata
        openapi_schema["tags"] = [
            {
                "name": "Menu Processing",
                "description": "Primary endpoints for processing holiday menus and generating grocery lists with timelines"
            },
            {
                "name": "Job Management",
                "description": "Endpoints for managing asynchronous processing jobs"
            },
            {
                "name": "Health Check",
                "description": "Service health and monitoring endpoints"
            },
            {
                "name": "Root",
                "description": "API root and information endpoints"
            }
        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi


# Create application instance
app = create_app()


# CLI entry point for running the server
def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info"
):
    """
    Run the FastAPI server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
        log_level: Logging level
    """
    logger.info(f"🚀 Starting Holiday Meal Planner API on {host}:{port}")

    uvicorn.run(
        "interfaces.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True
    )


if __name__ == "__main__":
    # Run with development settings
    run_server(reload=True)