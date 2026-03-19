"""
FastAPI response models for Holiday Meal Planner API.

Provides response schemas that match the OpenAPI specification,
with proper serialization for grocery lists and preparation timelines.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field

from core.models import (
    ConsolidatedGroceryList, Timeline, ProcessingMetadata,
    IngredientCategory, UnitEnum, TimingType
)


class APIStatus(str, Enum):
    """API response status values."""
    SUCCESS = "success"
    PENDING = "pending"
    FAILED = "failed"
    PROCESSING = "processing"


class JobStatus(str, Enum):
    """Asynchronous job status values."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngredientResponse(BaseModel):
    """Response model for individual ingredients."""
    name: str = Field(..., description="Ingredient name")
    quantity: float = Field(..., description="Quantity amount")
    unit: UnitEnum = Field(..., description="Unit of measurement")
    category: Optional[IngredientCategory] = Field(None, description="Food category")
    notes: Optional[str] = Field(None, description="Additional notes")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")

    class Config:
        schema_extra = {
            "example": {
                "name": "ground turkey",
                "quantity": 2.0,
                "unit": "pound",
                "category": "protein",
                "notes": "for stuffing",
                "confidence": 0.95
            }
        }


class GroceryListResponse(BaseModel):
    """Response model for consolidated grocery lists."""
    ingredients: List[IngredientResponse] = Field(..., description="List of consolidated ingredients")
    total_items: int = Field(..., description="Total number of ingredient items")
    estimated_cost_range: Optional[str] = Field(None, description="Estimated cost range")
    shopping_notes: List[str] = Field(default_factory=list, description="Shopping tips and notes")

    class Config:
        schema_extra = {
            "example": {
                "ingredients": [
                    {
                        "name": "ground turkey",
                        "quantity": 2.0,
                        "unit": "pound",
                        "category": "protein",
                        "confidence": 0.95
                    }
                ],
                "total_items": 12,
                "estimated_cost_range": "$45-65",
                "shopping_notes": ["Buy turkey from butcher counter for best quality"]
            }
        }


class PrepTaskResponse(BaseModel):
    """Response model for preparation tasks."""
    id: str = Field(..., description="Task identifier")
    dish_name: str = Field(..., description="Associated dish name")
    description: str = Field(..., description="Task description")
    estimated_duration: int = Field(..., description="Duration in minutes")
    timing_type: TimingType = Field(..., description="Timing category")
    dependencies: List[str] = Field(default_factory=list, description="Dependency task IDs")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence")

    class Config:
        schema_extra = {
            "example": {
                "id": "turkey_prep",
                "dish_name": "Roasted Turkey",
                "description": "Prepare and season turkey",
                "estimated_duration": 45,
                "timing_type": "day_before",
                "dependencies": [],
                "confidence": 0.88
            }
        }


class DayPlanResponse(BaseModel):
    """Response model for daily preparation plans."""
    day_offset: int = Field(..., description="Days before meal (0 = day of meal)")
    date: datetime = Field(..., description="Actual date for this day")
    tasks: List[PrepTaskResponse] = Field(..., description="Tasks for this day")
    total_duration: int = Field(..., description="Total duration in minutes")
    workload_level: int = Field(..., ge=1, le=5, description="Difficulty rating (1-5)")
    notes: Optional[str] = Field(None, description="Additional guidance")

    class Config:
        schema_extra = {
            "example": {
                "day_offset": 1,
                "date": "2026-11-27T00:00:00Z",
                "tasks": [
                    {
                        "id": "turkey_prep",
                        "dish_name": "Roasted Turkey",
                        "description": "Prepare and season turkey",
                        "estimated_duration": 45,
                        "timing_type": "day_before",
                        "confidence": 0.88
                    }
                ],
                "total_duration": 120,
                "workload_level": 3,
                "notes": "Heavy prep day"
            }
        }


class TimelineResponse(BaseModel):
    """Response model for preparation timelines."""
    meal_date: datetime = Field(..., description="Target meal date and time")
    days: List[DayPlanResponse] = Field(..., description="Day-by-day plans")
    critical_path: List[str] = Field(default_factory=list, description="Critical task IDs")
    total_prep_time: int = Field(..., description="Total preparation time in minutes")
    complexity_score: int = Field(..., ge=1, le=10, description="Complexity rating (1-10)")
    optimization_notes: List[str] = Field(default_factory=list, description="Scheduling notes")

    class Config:
        schema_extra = {
            "example": {
                "meal_date": "2026-11-28T14:00:00Z",
                "days": [
                    {
                        "day_offset": 1,
                        "date": "2026-11-27T00:00:00Z",
                        "tasks": [],
                        "total_duration": 120,
                        "workload_level": 3
                    }
                ],
                "critical_path": ["turkey_prep", "turkey_cook"],
                "total_prep_time": 480,
                "complexity_score": 6,
                "optimization_notes": ["Timeline optimized for balanced workload"]
            }
        }


class ProcessingMetadataResponse(BaseModel):
    """Response model for processing metadata."""
    total_processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    items_processed: int = Field(..., description="Successfully processed items")
    items_failed: int = Field(..., description="Failed items")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate")
    web_requests_made: int = Field(..., description="Web requests made")
    average_confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence")

    class Config:
        schema_extra = {
            "example": {
                "total_processing_time_ms": 15420,
                "items_processed": 4,
                "items_failed": 0,
                "success_rate": 1.0,
                "web_requests_made": 3,
                "average_confidence": 0.87
            }
        }


class FailedItemResponse(BaseModel):
    """Response model for failed processing items."""
    item_id: Optional[str] = Field(None, description="Item identifier")
    source_url: Optional[str] = Field(None, description="Original URL")
    description: Optional[str] = Field(None, description="Original description")
    error_message: str = Field(..., description="Error description")
    error_type: str = Field(..., description="Error category")
    retry_suggested: bool = Field(False, description="Whether retry is recommended")

    class Config:
        schema_extra = {
            "example": {
                "item_id": "item_3",
                "source_url": "https://example.com/broken-recipe",
                "error_message": "Recipe website returned 404",
                "error_type": "WebScrapingError",
                "retry_suggested": false
            }
        }


class ProcessingResultResponse(BaseModel):
    """Primary response model for menu processing results."""
    status: APIStatus = Field(default=APIStatus.SUCCESS, description="Processing status")
    grocery_list: GroceryListResponse = Field(..., description="Consolidated grocery list")
    timeline: Optional[TimelineResponse] = Field(None, description="Preparation timeline")
    processed_items: int = Field(..., description="Number of processed items")
    failed_items: List[FailedItemResponse] = Field(default_factory=list, description="Failed items")
    processing_metadata: ProcessingMetadataResponse = Field(..., description="Processing statistics")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "grocery_list": {
                    "ingredients": [
                        {
                            "name": "ground turkey",
                            "quantity": 2.0,
                            "unit": "pound",
                            "category": "protein",
                            "confidence": 0.95
                        }
                    ],
                    "total_items": 12,
                    "estimated_cost_range": "$45-65"
                },
                "timeline": {
                    "meal_date": "2026-11-28T14:00:00Z",
                    "days": [],
                    "total_prep_time": 480,
                    "complexity_score": 6
                },
                "processed_items": 4,
                "failed_items": [],
                "processing_metadata": {
                    "total_processing_time_ms": 15420,
                    "items_processed": 4,
                    "success_rate": 1.0
                }
            }
        }


class AsyncJobResponse(BaseModel):
    """Response model for asynchronous job initiation."""
    job_id: UUID = Field(..., description="Unique job identifier")
    status: JobStatus = Field(default=JobStatus.QUEUED, description="Current job status")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    status_url: str = Field(..., description="URL to check job status")

    class Config:
        schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "queued",
                "estimated_completion": "2026-03-18T15:05:00Z",
                "status_url": "/v1/jobs/123e4567-e89b-12d3-a456-426614174000"
            }
        }


class JobStatusResponse(BaseModel):
    """Response model for job status queries."""
    job_id: UUID = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current status")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Completion progress (0-1)")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    result: Optional[ProcessingResultResponse] = Field(None, description="Result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "completed",
                "progress": 1.0,
                "created_at": "2026-03-18T15:00:00Z",
                "updated_at": "2026-03-18T15:04:32Z",
                "result": {
                    "status": "success",
                    "grocery_list": {},
                    "processed_items": 4
                }
            }
        }


class ErrorDetailResponse(BaseModel):
    """Response model for detailed error information."""
    error_type: str = Field(..., description="Error category")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    suggestion: Optional[str] = Field(None, description="Suggested resolution")
    error_code: Optional[str] = Field(None, description="Internal error code")

    class Config:
        schema_extra = {
            "example": {
                "error_type": "ValidationError",
                "message": "Invalid meal date format",
                "details": {"field": "meal_datetime", "provided": "invalid-date"},
                "suggestion": "Use ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ",
                "error_code": "VAL_001"
            }
        }


class ValidationErrorResponse(BaseModel):
    """Response model for validation errors."""
    status: APIStatus = Field(default=APIStatus.FAILED)
    error: ErrorDetailResponse = Field(..., description="Error information")
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list, description="Field validation errors")

    class Config:
        schema_extra = {
            "example": {
                "status": "failed",
                "error": {
                    "error_type": "ValidationError",
                    "message": "Request validation failed",
                    "error_code": "VAL_001"
                },
                "validation_errors": [
                    {
                        "field": "meal_datetime",
                        "message": "Invalid datetime format",
                        "input": "invalid-date"
                    }
                ]
            }
        }


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Dependency status")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2026-03-18T15:00:00Z",
                "version": "1.0.0",
                "dependencies": {
                    "web_scraping": "operational",
                    "nlp_processing": "operational"
                }
            }
        }


# Convenience functions for converting core models to API responses

def grocery_list_to_response(grocery_list: ConsolidatedGroceryList) -> GroceryListResponse:
    """Convert core grocery list model to API response."""
    ingredients = [
        IngredientResponse(
            name=ing.name,
            quantity=ing.quantity,
            unit=ing.unit,
            category=ing.category,
            notes=ing.notes,
            confidence=ing.confidence
        )
        for ing in grocery_list.ingredients
    ]

    return GroceryListResponse(
        ingredients=ingredients,
        total_items=len(ingredients),
        estimated_cost_range=grocery_list.estimated_cost_range,
        shopping_notes=grocery_list.shopping_notes
    )


def timeline_to_response(timeline: Timeline) -> TimelineResponse:
    """Convert core timeline model to API response."""
    days = [
        DayPlanResponse(
            day_offset=day.day_offset,
            date=day.date,
            tasks=[
                PrepTaskResponse(
                    id=task.id,
                    dish_name=task.dish_name,
                    description=task.task_description,
                    estimated_duration=task.estimated_duration,
                    timing_type=task.timing_type,
                    dependencies=task.dependencies,
                    confidence=task.confidence
                )
                for task in day.tasks
            ],
            total_duration=day.total_duration,
            workload_level=day.workload_level,
            notes=day.notes
        )
        for day in timeline.days
    ]

    return TimelineResponse(
        meal_date=timeline.meal_date,
        days=days,
        critical_path=timeline.critical_path,
        total_prep_time=timeline.total_prep_time,
        complexity_score=timeline.complexity_score,
        optimization_notes=timeline.optimization_notes
    )


def metadata_to_response(metadata: ProcessingMetadata) -> ProcessingMetadataResponse:
    """Convert core metadata model to API response."""
    return ProcessingMetadataResponse(
        total_processing_time_ms=metadata.total_processing_time_ms,
        items_processed=metadata.items_processed,
        items_failed=metadata.items_failed,
        success_rate=metadata.success_rate,
        web_requests_made=metadata.web_requests_made,
        average_confidence=metadata.average_confidence
    )