"""
Process router for Holiday Meal Planner API.

Handles menu processing endpoints including synchronous and asynchronous
processing with grocery list generation and timeline planning.
"""

import asyncio
import logging
from typing import Annotated, Optional, List
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, validator

from core.models import MenuItemInput
from core.meal_planner import (
    MealPlannerOrchestrator, MealPlanningRequest
)
from core.agents.timeline_generator import TimelineGeneratorAgent, TimelineGenerationRequest
from interfaces.api.dependencies import (
    rate_limited, validated_context, validate_menu_request,
    validate_meal_datetime, validate_timeline_params, APIErrorHandler
)
from interfaces.api.responses import (
    ProcessingResultResponse, AsyncJobResponse, ErrorDetailResponse,
    grocery_list_to_response, timeline_to_response, metadata_to_response,
    FailedItemResponse, APIStatus, JobStatus
)
from shared.exceptions import MealPlannerException


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["Menu Processing"])

# In-memory job storage (use Redis or database in production)
_job_storage: dict = {}


class MenuItemRequest(BaseModel):
    """Request model for individual menu items."""
    source_url: Optional[str] = Field(None, description="Recipe URL (HTTPS only)")
    description: Optional[str] = Field(None, description="Free-text dish description")
    serving_size: int = Field(8, ge=1, le=100, description="Number of people served")

    @validator('source_url')
    def validate_https_url(cls, v):
        """Ensure URL uses HTTPS for security."""
        if v and not v.startswith('https://'):
            raise ValueError("URLs must use HTTPS protocol for security")
        return v

    class Config:
        schema_extra = {
            "example": {
                "source_url": "https://allrecipes.com/recipe/turkey-stuffing",
                "serving_size": 8
            }
        }


class MenuProcessRequest(BaseModel):
    """Request model for menu processing."""
    menu_items: List[MenuItemRequest] = Field(..., min_items=1, max_items=20)
    meal_datetime: Optional[datetime] = Field(None, description="Target meal date and time")
    max_prep_days: Optional[int] = Field(7, ge=1, le=14, description="Maximum preparation days")
    max_daily_hours: Optional[int] = Field(4, ge=1, le=12, description="Maximum hours per day")
    confidence_threshold: float = Field(0.6, ge=0.0, le=1.0, description="Ingredient confidence threshold")
    similarity_threshold: float = Field(85.0, ge=0.0, le=100.0, description="Ingredient similarity threshold")
    include_timeline: bool = Field(True, description="Generate preparation timeline")

    class Config:
        schema_extra = {
            "example": {
                "menu_items": [
                    {
                        "source_url": "https://allrecipes.com/recipe/turkey-stuffing",
                        "serving_size": 8
                    },
                    {
                        "description": "mashed potatoes for 10 people with butter and cream",
                        "serving_size": 10
                    }
                ],
                "meal_datetime": "2026-11-28T14:00:00Z",
                "max_prep_days": 3,
                "max_daily_hours": 4,
                "include_timeline": True
            }
        }


@router.post(
    "/",
    response_model=ProcessingResultResponse,
    summary="Process holiday menu",
    description="Process a collection of holiday dishes and generate consolidated grocery list with timeline",
    responses={
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        429: {"description": "Rate Limit Exceeded"},
        500: {"description": "Internal Server Error"}
    }
)
async def process_menu(
    request: MenuProcessRequest,
    _: Annotated[None, rate_limited()],
    context: Annotated[dict, validated_context()]
) -> ProcessingResultResponse:
    """
    Process holiday menu and generate grocery list with timeline.

    This endpoint processes a collection of holiday dishes (URLs and/or descriptions)
    and returns a consolidated grocery list with optional day-by-day preparation timeline.

    Args:
        request: Menu processing request with dishes and parameters
        _: Rate limiting dependency
        context: Request context for logging

    Returns:
        Processing result with grocery list and timeline

    Raises:
        HTTPException: For various error conditions
    """
    try:
        logger.info(f"Processing menu request with {len(request.menu_items)} items")

        # Validate request
        menu_items_data = [item.dict() for item in request.menu_items]
        await validate_menu_request(menu_items_data)

        # Validate meal datetime
        validated_meal_datetime = await validate_meal_datetime(request.meal_datetime)

        # Validate timeline parameters
        validated_prep_days, validated_daily_hours = await validate_timeline_params(
            request.max_prep_days, request.max_daily_hours
        )

        # Convert request items to core models
        core_menu_items = []
        for item in request.menu_items:
            if item.source_url:
                core_item = MenuItemInput(
                    source_url=item.source_url,
                    serving_size=item.serving_size
                )
            else:
                core_item = MenuItemInput(
                    description=item.description,
                    serving_size=item.serving_size
                )
            core_menu_items.append(core_item)

        # Create meal planning request
        meal_planning_request = MealPlanningRequest(
            menu_items=core_menu_items,
            serving_size=max(item.serving_size for item in request.menu_items),
            confidence_threshold=request.confidence_threshold,
            similarity_threshold=request.similarity_threshold,
            include_timeline=request.include_timeline,
            meal_datetime=validated_meal_datetime,
            max_prep_days=validated_prep_days,
            max_daily_hours=validated_daily_hours
        )

        # Process meal plan
        orchestrator = MealPlannerOrchestrator()
        planning_response = await orchestrator.plan_meal(meal_planning_request)

        # Convert core models to API responses
        grocery_list_response = grocery_list_to_response(
            planning_response.processing_result.grocery_list
        )

        timeline_response = None
        if planning_response.processing_result.prep_timeline.days:
            timeline_response = timeline_to_response(
                planning_response.processing_result.prep_timeline
            )

        metadata_response = metadata_to_response(
            planning_response.processing_result.processing_metadata
        )

        # Convert failed items
        failed_items_response = []
        for failed_item in planning_response.processing_result.failed_items:
            failed_items_response.append(
                FailedItemResponse(
                    item_id=failed_item.get('id'),
                    source_url=failed_item.get('source_url'),
                    description=failed_item.get('description'),
                    error_message=failed_item.get('error_message', 'Unknown error'),
                    error_type=failed_item.get('error_type', 'ProcessingError'),
                    retry_suggested=failed_item.get('retry_suggested', False)
                )
            )

        # Build response
        response = ProcessingResultResponse(
            status=APIStatus.SUCCESS,
            grocery_list=grocery_list_response,
            timeline=timeline_response,
            processed_items=len(planning_response.processing_result.processed_items),
            failed_items=failed_items_response,
            processing_metadata=metadata_response
        )

        logger.info(f"Menu processing completed successfully: {response.processed_items} items processed")
        return response

    except HTTPException:
        # Re-raise HTTP exceptions from dependencies
        raise

    except MealPlannerException as e:
        # Handle application-specific exceptions
        logger.error(f"Meal planner error: {e}")
        raise APIErrorHandler.handle_meal_planner_exception(e)

    except Exception as e:
        # Handle unexpected exceptions
        logger.error(f"Unexpected error in process_menu: {e}", exc_info=True)
        raise APIErrorHandler.handle_generic_exception(e)


@router.post(
    "/async",
    response_model=AsyncJobResponse,
    summary="Start asynchronous menu processing",
    description="Initiate background processing for large menus, returns job ID for status polling",
    responses={
        202: {"description": "Processing Started"},
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        429: {"description": "Rate Limit Exceeded"}
    }
)
async def process_menu_async(
    request: MenuProcessRequest,
    _: Annotated[None, rate_limited()],
    context: Annotated[dict, validated_context()]
) -> AsyncJobResponse:
    """
    Start asynchronous menu processing for large menus.

    This endpoint initiates background processing and returns a job ID
    for status polling. Useful for large menus or slow recipe websites.

    Args:
        request: Menu processing request
        _: Rate limiting dependency
        context: Request context for logging

    Returns:
        Async job response with job ID and status URL

    Raises:
        HTTPException: For validation errors
    """
    try:
        logger.info(f"Starting async menu processing with {len(request.menu_items)} items")

        # Validate request
        menu_items_data = [item.dict() for item in request.menu_items]
        await validate_menu_request(menu_items_data)

        # Validate meal datetime
        validated_meal_datetime = await validate_meal_datetime(request.meal_datetime)

        # Generate job ID
        job_id = uuid4()

        # Store job with initial status
        job_data = {
            "job_id": job_id,
            "status": JobStatus.QUEUED,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "request": request.dict(),
            "progress": 0.0,
            "result": None,
            "error": None
        }

        _job_storage[str(job_id)] = job_data

        # Start background processing (in production, use Celery or similar)
        asyncio.create_task(_process_menu_background(job_id, request, context))

        # Return job response
        response = AsyncJobResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            estimated_completion=datetime.utcnow().replace(microsecond=0),
            status_url=f"/v1/jobs/{job_id}"
        )

        logger.info(f"Async processing job {job_id} queued")
        return response

    except HTTPException:
        # Re-raise HTTP exceptions from dependencies
        raise

    except Exception as e:
        logger.error(f"Error starting async processing: {e}", exc_info=True)
        raise APIErrorHandler.handle_generic_exception(e)


async def _process_menu_background(
    job_id: str,
    request: MenuProcessRequest,
    context: dict
) -> None:
    """
    Background task for processing menu asynchronously.

    Args:
        job_id: Job identifier
        request: Original processing request
        context: Request context
    """
    try:
        # Update job status to processing
        job_data = _job_storage[job_id]
        job_data.update({
            "status": JobStatus.PROCESSING,
            "updated_at": datetime.utcnow(),
            "progress": 0.1
        })

        logger.info(f"Starting background processing for job {job_id}")

        # Convert request to core models (similar to sync endpoint)
        core_menu_items = []
        for item in request.menu_items:
            if item.source_url:
                core_item = MenuItemInput(
                    source_url=item.source_url,
                    serving_size=item.serving_size
                )
            else:
                core_item = MenuItemInput(
                    description=item.description,
                    serving_size=item.serving_size
                )
            core_menu_items.append(core_item)

        # Update progress
        job_data["progress"] = 0.3

        # Validate parameters
        validated_meal_datetime = await validate_meal_datetime(request.meal_datetime)
        validated_prep_days, validated_daily_hours = await validate_timeline_params(
            request.max_prep_days, request.max_daily_hours
        )

        # Create meal planning request
        meal_planning_request = MealPlanningRequest(
            menu_items=core_menu_items,
            serving_size=max(item.serving_size for item in request.menu_items),
            confidence_threshold=request.confidence_threshold,
            similarity_threshold=request.similarity_threshold,
            include_timeline=request.include_timeline,
            meal_datetime=validated_meal_datetime,
            max_prep_days=validated_prep_days,
            max_daily_hours=validated_daily_hours
        )

        # Update progress
        job_data["progress"] = 0.5

        # Process meal plan
        orchestrator = MealPlannerOrchestrator()
        planning_response = await orchestrator.plan_meal(meal_planning_request)

        # Update progress
        job_data["progress"] = 0.8

        # Convert to API response format (same as sync endpoint)
        grocery_list_response = grocery_list_to_response(
            planning_response.processing_result.grocery_list
        )

        timeline_response = None
        if planning_response.processing_result.prep_timeline.days:
            timeline_response = timeline_to_response(
                planning_response.processing_result.prep_timeline
            )

        metadata_response = metadata_to_response(
            planning_response.processing_result.processing_metadata
        )

        failed_items_response = []
        for failed_item in planning_response.processing_result.failed_items:
            failed_items_response.append(
                FailedItemResponse(
                    item_id=failed_item.get('id'),
                    source_url=failed_item.get('source_url'),
                    description=failed_item.get('description'),
                    error_message=failed_item.get('error_message', 'Unknown error'),
                    error_type=failed_item.get('error_type', 'ProcessingError'),
                    retry_suggested=failed_item.get('retry_suggested', False)
                )
            )

        # Build final result
        result = ProcessingResultResponse(
            status=APIStatus.SUCCESS,
            grocery_list=grocery_list_response,
            timeline=timeline_response,
            processed_items=len(planning_response.processing_result.processed_items),
            failed_items=failed_items_response,
            processing_metadata=metadata_response
        )

        # Update job with completed result
        job_data.update({
            "status": JobStatus.COMPLETED,
            "updated_at": datetime.utcnow(),
            "progress": 1.0,
            "result": result.dict()
        })

        logger.info(f"Background processing completed for job {job_id}")

    except Exception as e:
        # Update job with error status
        logger.error(f"Background processing failed for job {job_id}: {e}", exc_info=True)

        job_data = _job_storage.get(job_id)
        if job_data:
            job_data.update({
                "status": JobStatus.FAILED,
                "updated_at": datetime.utcnow(),
                "error": str(e)
            })


# Export job storage for jobs router
def get_job_storage():
    """Get reference to job storage for jobs router."""
    return _job_storage