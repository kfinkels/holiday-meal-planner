"""
Shared service layer for Holiday Meal Planner.

Provides unified business logic between CLI and API interfaces,
ensuring identical results regardless of access method.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta

from core.models import MenuItemInput, ProcessingResult
from core.meal_planner import MealPlannerOrchestrator, MealPlanningRequest
from core.agents.timeline_generator import TimelineGeneratorAgent, TimelineGenerationRequest
from shared.exceptions import MealPlannerException, ValidationError as AppValidationError
from shared.config import get_settings


logger = logging.getLogger(__name__)


class ServiceLayerError(MealPlannerException):
    """Exception raised by service layer operations."""
    pass


class MealPlanningService:
    """
    Unified service for meal planning operations.

    Provides a single interface for meal planning functionality
    that can be used by both CLI and API layers.
    """

    def __init__(self):
        """Initialize the meal planning service."""
        self.settings = get_settings()
        self.orchestrator = MealPlannerOrchestrator()
        self._timeline_generator = None

    @property
    def timeline_generator(self) -> TimelineGeneratorAgent:
        """Lazy-loaded timeline generator."""
        if self._timeline_generator is None:
            self._timeline_generator = TimelineGeneratorAgent()
        return self._timeline_generator

    async def process_menu_items(
        self,
        menu_items: List[Dict[str, Any]],
        serving_size: Optional[int] = None,
        confidence_threshold: float = 0.6,
        similarity_threshold: float = 85.0,
        include_timeline: bool = False,
        meal_datetime: Optional[datetime] = None,
        max_prep_days: int = 7,
        max_daily_hours: int = 4
    ) -> ProcessingResult:
        """
        Process menu items and generate grocery list with optional timeline.

        This is the main entry point for meal planning functionality,
        used by both CLI and API interfaces to ensure consistent results.

        Args:
            menu_items: List of menu item dictionaries with source_url or description
            serving_size: Override serving size for all items
            confidence_threshold: Minimum ingredient confidence threshold
            similarity_threshold: Ingredient similarity threshold for consolidation
            include_timeline: Whether to generate preparation timeline
            meal_datetime: Target meal date and time
            max_prep_days: Maximum preparation days
            max_daily_hours: Maximum daily hours

        Returns:
            Complete processing result with grocery list and timeline

        Raises:
            ServiceLayerError: If processing fails
            AppValidationError: If input validation fails
        """
        try:
            logger.info(f"Processing {len(menu_items)} menu items via service layer")

            # Validate input
            validated_items = self._validate_and_convert_menu_items(
                menu_items, serving_size
            )

            # Validate timeline parameters if timeline requested
            if include_timeline:
                validated_meal_datetime = self._validate_meal_datetime(meal_datetime)
                validated_prep_days, validated_daily_hours = self._validate_timeline_params(
                    max_prep_days, max_daily_hours
                )
            else:
                validated_meal_datetime = None
                validated_prep_days = max_prep_days
                validated_daily_hours = max_daily_hours

            # Create meal planning request
            planning_request = MealPlanningRequest(
                menu_items=validated_items,
                serving_size=serving_size or 8,
                confidence_threshold=confidence_threshold,
                similarity_threshold=similarity_threshold,
                include_timeline=include_timeline,
                meal_datetime=validated_meal_datetime,
                max_prep_days=validated_prep_days,
                max_daily_hours=validated_daily_hours
            )

            # Execute meal planning
            planning_response = await self.orchestrator.plan_meal(planning_request)

            logger.info("Meal processing completed successfully via service layer")
            return planning_response.processing_result

        except Exception as e:
            logger.error(f"Service layer processing failed: {e}", exc_info=True)
            if isinstance(e, (MealPlannerException, AppValidationError)):
                raise
            else:
                raise ServiceLayerError(f"Meal planning service failed: {e}")

    async def process_single_item(
        self,
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        serving_size: int = 8,
        confidence_threshold: float = 0.6,
        similarity_threshold: float = 85.0
    ) -> ProcessingResult:
        """
        Process a single menu item (convenience method).

        Args:
            source_url: Recipe URL (HTTPS only)
            description: Free-text description
            serving_size: Number of people to serve
            confidence_threshold: Minimum ingredient confidence threshold
            similarity_threshold: Ingredient similarity threshold

        Returns:
            Processing result with grocery list

        Raises:
            ServiceLayerError: If processing fails
            AppValidationError: If input validation fails
        """
        if not source_url and not description:
            raise AppValidationError("Either source_url or description must be provided")

        menu_item = {}
        if source_url:
            menu_item["source_url"] = source_url
        if description:
            menu_item["description"] = description
        menu_item["serving_size"] = serving_size

        return await self.process_menu_items(
            menu_items=[menu_item],
            confidence_threshold=confidence_threshold,
            similarity_threshold=similarity_threshold,
            include_timeline=False
        )

    async def generate_timeline_only(
        self,
        menu_items: List[Dict[str, Any]],
        meal_datetime: datetime,
        max_prep_days: int = 7,
        max_daily_hours: int = 4,
        confidence_threshold: float = 0.6
    ) -> ProcessingResult:
        """
        Generate timeline for menu items without full processing.

        Args:
            menu_items: List of menu item dictionaries
            meal_datetime: Target meal date and time
            max_prep_days: Maximum preparation days
            max_daily_hours: Maximum daily hours
            confidence_threshold: Minimum confidence threshold

        Returns:
            Processing result with timeline

        Raises:
            ServiceLayerError: If timeline generation fails
        """
        try:
            logger.info(f"Generating timeline for {len(menu_items)} items")

            # Validate input
            validated_items = self._validate_and_convert_menu_items(menu_items)
            validated_meal_datetime = self._validate_meal_datetime(meal_datetime)
            validated_prep_days, validated_daily_hours = self._validate_timeline_params(
                max_prep_days, max_daily_hours
            )

            # Create timeline generation request
            timeline_request = TimelineGenerationRequest(
                menu_items=validated_items,
                meal_datetime=validated_meal_datetime,
                max_prep_days=validated_prep_days,
                max_daily_hours=validated_daily_hours,
                confidence_threshold=confidence_threshold
            )

            # Generate timeline
            timeline_response = await self.timeline_generator.generate_timeline(
                timeline_request
            )

            # Create minimal processing result with timeline
            from core.models import (
                ConsolidatedGroceryList, ProcessingMetadata, Ingredient
            )

            # Create empty grocery list
            empty_grocery_list = ConsolidatedGroceryList(
                ingredients=[],
                total_estimated_cost=0.0,
                estimated_cost_range="N/A",
                shopping_notes=["Timeline generated without grocery list processing"]
            )

            # Create minimal metadata
            minimal_metadata = ProcessingMetadata(
                total_processing_time_ms=100,
                items_processed=len(menu_items),
                items_failed=0,
                success_rate=1.0,
                web_requests_made=0,
                average_confidence=confidence_threshold
            )

            result = ProcessingResult(
                grocery_list=empty_grocery_list,
                prep_timeline=timeline_response.timeline,
                processed_items=validated_items,
                failed_items=[],
                processing_metadata=minimal_metadata
            )

            logger.info("Timeline generation completed successfully")
            return result

        except Exception as e:
            logger.error(f"Timeline generation failed: {e}", exc_info=True)
            if isinstance(e, MealPlannerException):
                raise
            else:
                raise ServiceLayerError(f"Timeline generation failed: {e}")

    def _validate_and_convert_menu_items(
        self,
        menu_items: List[Dict[str, Any]],
        override_serving_size: Optional[int] = None
    ) -> List[MenuItemInput]:
        """
        Validate and convert menu items to core models.

        Args:
            menu_items: List of menu item dictionaries
            override_serving_size: Override serving size for all items

        Returns:
            List of validated MenuItemInput objects

        Raises:
            AppValidationError: If validation fails
        """
        if not menu_items:
            raise AppValidationError("At least one menu item is required")

        if len(menu_items) > 20:
            raise AppValidationError("Maximum 20 menu items allowed")

        validated_items = []

        for i, item in enumerate(menu_items):
            try:
                # Check required fields
                source_url = item.get("source_url")
                description = item.get("description")

                if not source_url and not description:
                    raise AppValidationError(
                        f"Menu item {i}: Either source_url or description must be provided"
                    )

                # Validate URL security
                if source_url:
                    if not source_url.startswith("https://"):
                        raise AppValidationError(
                            f"Menu item {i}: URLs must use HTTPS protocol"
                        )

                    if len(source_url) > 2048:
                        raise AppValidationError(
                            f"Menu item {i}: URL too long (max 2048 characters)"
                        )

                # Validate description
                if description and len(description) > 500:
                    raise AppValidationError(
                        f"Menu item {i}: Description too long (max 500 characters)"
                    )

                # Validate serving size
                serving_size = override_serving_size or item.get("serving_size", 8)
                if not isinstance(serving_size, int) or serving_size < 1 or serving_size > 100:
                    raise AppValidationError(
                        f"Menu item {i}: Serving size must be between 1 and 100"
                    )

                # Create validated menu item
                if source_url:
                    core_item = MenuItemInput(
                        source_url=source_url,
                        serving_size=serving_size
                    )
                else:
                    core_item = MenuItemInput(
                        description=description,
                        serving_size=serving_size
                    )

                validated_items.append(core_item)

            except Exception as e:
                if isinstance(e, AppValidationError):
                    raise
                else:
                    raise AppValidationError(f"Menu item {i} validation failed: {e}")

        return validated_items

    def _validate_meal_datetime(self, meal_datetime: Optional[datetime]) -> datetime:
        """
        Validate meal datetime parameter.

        Args:
            meal_datetime: Meal date and time to validate

        Returns:
            Validated datetime or default if None

        Raises:
            AppValidationError: If datetime is invalid
        """
        if meal_datetime is None:
            # Default to next Sunday at 6 PM
            today = datetime.utcnow()
            days_ahead = 6 - today.weekday()  # Sunday = 6
            if days_ahead <= 0:
                days_ahead += 7
            default_datetime = today + timedelta(days=days_ahead)
            return default_datetime.replace(hour=18, minute=0, second=0, microsecond=0)

        # Check if date is in the future
        if meal_datetime <= datetime.utcnow():
            raise AppValidationError("Meal date must be in the future")

        # Check if date is not too far in the future (1 year max)
        max_future_date = datetime.utcnow() + timedelta(days=365)
        if meal_datetime > max_future_date:
            raise AppValidationError("Meal date cannot be more than 1 year in the future")

        return meal_datetime

    def _validate_timeline_params(
        self,
        max_prep_days: int,
        max_daily_hours: int
    ) -> tuple[int, int]:
        """
        Validate timeline generation parameters.

        Args:
            max_prep_days: Maximum preparation days
            max_daily_hours: Maximum daily hours

        Returns:
            Tuple of validated (max_prep_days, max_daily_hours)

        Raises:
            AppValidationError: If parameters are invalid
        """
        if max_prep_days < 1 or max_prep_days > 14:
            raise AppValidationError("max_prep_days must be between 1 and 14")

        if max_daily_hours < 1 or max_daily_hours > 12:
            raise AppValidationError("max_daily_hours must be between 1 and 12")

        return max_prep_days, max_daily_hours


# Global service instance for easy access
_meal_planning_service: Optional[MealPlanningService] = None


def get_meal_planning_service() -> MealPlanningService:
    """
    Get the global meal planning service instance.

    Returns:
        Singleton meal planning service instance
    """
    global _meal_planning_service
    if _meal_planning_service is None:
        _meal_planning_service = MealPlanningService()
    return _meal_planning_service


# Convenience functions that both CLI and API can use

async def process_meal_plan(
    menu_items: List[Dict[str, Any]],
    **kwargs
) -> ProcessingResult:
    """
    Convenience function for processing meal plans.

    Args:
        menu_items: List of menu item dictionaries
        **kwargs: Additional parameters for processing

    Returns:
        Processing result with grocery list and optional timeline
    """
    service = get_meal_planning_service()
    return await service.process_menu_items(menu_items, **kwargs)


async def process_single_recipe(
    source_url: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs
) -> ProcessingResult:
    """
    Convenience function for processing single recipes.

    Args:
        source_url: Recipe URL
        description: Recipe description
        **kwargs: Additional parameters for processing

    Returns:
        Processing result with grocery list
    """
    service = get_meal_planning_service()
    return await service.process_single_item(source_url, description, **kwargs)


async def generate_meal_timeline(
    menu_items: List[Dict[str, Any]],
    meal_datetime: datetime,
    **kwargs
) -> ProcessingResult:
    """
    Convenience function for generating meal timelines.

    Args:
        menu_items: List of menu item dictionaries
        meal_datetime: Target meal date and time
        **kwargs: Additional parameters for timeline generation

    Returns:
        Processing result with timeline
    """
    service = get_meal_planning_service()
    return await service.generate_timeline_only(menu_items, meal_datetime, **kwargs)