"""
Pydantic data models for Holiday Meal Planner.

Based on data-model.md specification, these models provide type safety,
validation, and serialization for the entire meal planning pipeline.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator, model_validator
from pydantic import HttpUrl


class UnitEnum(str, Enum):
    """Standardized units of measurement for ingredients."""

    # Volume units
    CUP = "cup"
    TABLESPOON = "tablespoon"
    TEASPOON = "teaspoon"
    FLUID_OUNCE = "fluid_ounce"
    PINT = "pint"
    QUART = "quart"
    GALLON = "gallon"
    LITER = "liter"
    MILLILITER = "milliliter"

    # Weight units
    POUND = "pound"
    OUNCE = "ounce"
    GRAM = "gram"
    KILOGRAM = "kilogram"

    # Count units
    WHOLE = "whole"
    PIECE = "piece"
    CLOVE = "clove"
    BUNCH = "bunch"
    PACKAGE = "package"

    # Special units
    TO_TASTE = "to_taste"
    PINCH = "pinch"
    DASH = "dash"


class IngredientCategory(str, Enum):
    """Food categories for ingredient organization."""

    PROTEIN = "protein"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    DAIRY = "dairy"
    GRAIN = "grain"
    HERB = "herb"
    SPICE = "spice"
    FAT = "fat"
    OTHER = "other"


class TimingType(str, Enum):
    """Categories of timing constraints for preparation tasks."""

    MAKE_AHEAD = "make_ahead"      # Can be done days in advance
    DAY_BEFORE = "day_before"      # Should be done 12-24 hours prior
    DAY_OF_EARLY = "day_of_early"  # Morning of meal day
    DAY_OF_LATE = "day_of_late"    # Within 4 hours of meal
    IMMEDIATE = "immediate"        # Must be done just before serving


class MenuItemInput(BaseModel):
    """Represents user input for a single dish in the holiday menu."""

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    source_url: Optional[HttpUrl] = Field(None, description="Recipe URL for web extraction")
    description: Optional[str] = Field(None, description="Free-text description of the dish")
    serving_size: int = Field(8, description="Number of people this dish serves")

    @model_validator(mode='after')
    def validate_input_source(self):
        """Ensure either source_url OR description is provided."""
        if not self.source_url and not self.description:
            raise ValueError("Must provide either source_url or description")
        return self

    @validator('source_url')
    def validate_https_only(cls, v):
        """Ensure URL uses HTTPS protocol for security."""
        if v and not str(v).startswith('https://'):
            raise ValueError("URL must use HTTPS protocol")
        return v

    @validator('serving_size')
    def validate_serving_size(cls, v):
        """Validate serving size is reasonable."""
        if v < 1 or v > 100:
            raise ValueError("Serving size must be between 1 and 100")
        return v


class Ingredient(BaseModel):
    """Represents a single ingredient with standardized quantity and unit."""

    name: str = Field(..., description="Canonical ingredient name (normalized)")
    quantity: float = Field(..., description="Numeric amount required")
    unit: UnitEnum = Field(..., description="Standardized unit of measurement")
    category: Optional[IngredientCategory] = Field(None, description="Food category for organization")
    confidence: float = Field(..., description="Extraction confidence score (0.0-1.0)")
    original_text: Optional[str] = Field(None, description="Original extracted text for reference")

    @validator('quantity')
    def validate_positive_quantity(cls, v):
        """Ensure quantity is positive."""
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v

    @validator('confidence')
    def validate_confidence_range(cls, v):
        """Ensure confidence is between 0.0 and 1.0."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @validator('name')
    def validate_non_empty_name(cls, v):
        """Ensure name is not empty after stripping."""
        if not v.strip():
            raise ValueError("Ingredient name cannot be empty")
        return v.strip()


class ConsolidatedGroceryList(BaseModel):
    """Represents the final consolidated shopping list with optimized quantities."""

    ingredients: List[Ingredient] = Field(..., description="List of consolidated ingredients")
    total_items: int = Field(..., description="Count of unique ingredients")
    consolidation_notes: List[str] = Field(default_factory=list, description="List of merging decisions made")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of list generation")
    serving_size: int = Field(..., description="Total serving size for entire menu")

    @validator('ingredients')
    def validate_non_empty_ingredients(cls, v):
        """Ensure ingredients list is not empty."""
        if not v:
            raise ValueError("Ingredients list cannot be empty")
        return v

    @model_validator(mode='after')
    def validate_total_items_matches(self):
        """Ensure total_items matches ingredients list length."""
        if self.total_items != len(self.ingredients):
            raise ValueError(f"total_items ({self.total_items}) must match ingredients list length ({len(self.ingredients)})")
        return self


class PrepTask(BaseModel):
    """Represents a single preparation task with timing and dependency information."""

    id: str = Field(..., description="Unique task identifier")
    dish_name: str = Field(..., description="Name of associated dish")
    task_description: str = Field(..., description="What needs to be done")
    estimated_duration: int = Field(..., description="Time in minutes")
    dependencies: List[str] = Field(default_factory=list, description="List of task IDs that must complete first")
    timing_type: TimingType = Field(..., description="Category of timing constraint")
    optimal_timing: Optional[str] = Field(None, description="When task should ideally be performed relative to meal")
    confidence: float = Field(..., description="AI confidence in task details")

    @validator('estimated_duration')
    def validate_positive_duration(cls, v):
        """Ensure estimated duration is positive."""
        if v <= 0:
            raise ValueError("Estimated duration must be positive")
        return v

    @validator('confidence')
    def validate_confidence_range(cls, v):
        """Ensure confidence is between 0.0 and 1.0."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v


class DayPlan(BaseModel):
    """Represents preparation tasks scheduled for a specific day."""

    day_offset: int = Field(..., description="Days before meal (0 = day of meal)")
    date: datetime = Field(..., description="Actual calendar date")
    tasks: List[PrepTask] = Field(default_factory=list, description="List of PrepTask objects scheduled for this day")
    total_duration: int = Field(..., description="Sum of all task durations in minutes")
    workload_level: int = Field(..., description="Subjective difficulty rating (1-5 scale)")
    notes: Optional[str] = Field(None, description="Additional guidance for the day")

    @validator('day_offset')
    def validate_day_offset_range(cls, v):
        """Ensure day offset is reasonable."""
        if v < 0 or v > 7:
            raise ValueError("Day offset must be between 0 and 7")
        return v

    @validator('workload_level')
    def validate_workload_level_range(cls, v):
        """Ensure workload level is in valid range."""
        if v < 1 or v > 5:
            raise ValueError("Workload level must be between 1 and 5")
        return v

    @validator('total_duration')
    def validate_reasonable_duration(cls, v):
        """Warn if total duration exceeds 4 hours."""
        if v > 240:  # 4 hours
            # In a real implementation, this might log a warning
            pass
        return v


class Timeline(BaseModel):
    """Represents the complete day-by-day preparation schedule."""

    meal_date: datetime = Field(..., description="Target date and time for the meal")
    days: List[DayPlan] = Field(..., description="List of DayPlan objects ordered by day_offset")
    critical_path: List[str] = Field(default_factory=list, description="List of task IDs on the critical path")
    total_prep_time: int = Field(..., description="Sum of all preparation time across all days")
    complexity_score: int = Field(..., description="Overall difficulty rating (1-10 scale)")
    optimization_notes: List[str] = Field(default_factory=list, description="Explanation of scheduling decisions")

    @validator('meal_date')
    def validate_future_date(cls, v):
        """Ensure meal date is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("Meal date must be in the future")
        return v

    @validator('complexity_score')
    def validate_complexity_score_range(cls, v):
        """Ensure complexity score is in valid range."""
        if v < 1 or v > 10:
            raise ValueError("Complexity score must be between 1 and 10")
        return v

    @validator('days')
    def validate_days_ordering(cls, v):
        """Ensure days are ordered by day_offset (descending)."""
        if len(v) > 1:
            day_offsets = [day.day_offset for day in v]
            if day_offsets != sorted(day_offsets, reverse=True):
                raise ValueError("Days must be ordered by day_offset (descending)")
        return v


class ProcessingMetadata(BaseModel):
    """Statistics and performance information about processing."""

    total_processing_time_ms: int = Field(..., description="Total processing time in milliseconds")
    items_processed: int = Field(..., description="Number of items successfully processed")
    items_failed: int = Field(..., description="Number of items that failed processing")
    success_rate: float = Field(..., description="Success rate (0.0-1.0)")
    web_requests_made: int = Field(..., description="Number of web requests made")
    average_confidence: float = Field(..., description="Average confidence score")

    @validator('success_rate', 'average_confidence')
    def validate_rate_range(cls, v):
        """Ensure rates are between 0.0 and 1.0."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Rate must be between 0.0 and 1.0")
        return v


class ProcessingResult(BaseModel):
    """Represents the complete output of the meal planning pipeline."""

    grocery_list: ConsolidatedGroceryList = Field(..., description="ConsolidatedGroceryList object")
    prep_timeline: Timeline = Field(..., description="Timeline object")
    processed_items: List[MenuItemInput] = Field(..., description="List of successfully processed MenuItemInput")
    failed_items: List[Dict[str, Any]] = Field(default_factory=list, description="List of items that failed processing with error messages")
    processing_metadata: ProcessingMetadata = Field(..., description="Statistics and performance information")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of result generation")

    @validator('processed_items')
    def validate_at_least_one_processed(cls, v):
        """Ensure at least one item was successfully processed."""
        if not v:
            raise ValueError("Must have at least one successfully processed item")
        return v


# Additional models for API responses and error handling

class ProcessedMenuItem(MenuItemInput):
    """Extended MenuItemInput with processing metadata."""

    extracted_title: Optional[str] = Field(None, description="Extracted recipe title")
    ingredients_count: int = Field(0, description="Number of ingredients extracted")
    processing_time_ms: int = Field(0, description="Processing time in milliseconds")


class FailedMenuItem(MenuItemInput):
    """MenuItemInput with error information."""

    error_message: str = Field(..., description="Error message describing the failure")
    error_code: str = Field(..., description="Error code for categorization")
    retry_suggested: bool = Field(False, description="Whether retry is suggested")


# Configuration and pipeline state models

class PipelineState(BaseModel):
    """Internal state management for the multi-agent pipeline."""

    menu_items: List[MenuItemInput] = Field(default_factory=list, description="Input menu items")
    processed_ingredients: Dict[str, List[Ingredient]] = Field(default_factory=dict, description="Ingredients by menu item")
    consolidated_ingredients: List[Ingredient] = Field(default_factory=list, description="Final consolidated ingredients")
    prep_tasks: List[PrepTask] = Field(default_factory=list, description="Generated preparation tasks")
    processing_errors: List[str] = Field(default_factory=list, description="Accumulated errors")
    current_phase: str = Field("initialized", description="Current processing phase")

    def add_error(self, error: str) -> None:
        """Add an error to the processing errors list."""
        self.processing_errors.append(error)

    def has_errors(self) -> bool:
        """Check if there are any processing errors."""
        return len(self.processing_errors) > 0