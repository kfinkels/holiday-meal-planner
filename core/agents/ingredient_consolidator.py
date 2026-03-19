"""
Ingredient Consolidator Agent for Holiday Meal Planner.

PydanticAI agent that manages ingredient deduplication and unit normalization
using fuzzy matching and intelligent consolidation strategies.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

from core.models import Ingredient, ConsolidatedGroceryList, IngredientCategory, UnitEnum
from core.services.consolidator import IngredientConsolidator
from shared.exceptions import IngredientConsolidationError, AgentError
from shared.config import get_settings


logger = logging.getLogger(__name__)


class ConsolidationRequest(BaseModel):
    """Request model for ingredient consolidation."""
    ingredients: List[Ingredient]
    serving_size: int = 8
    consolidation_strategy: str = "fuzzy_matching"  # fuzzy_matching, exact_match, category_based
    similarity_threshold: float = 85.0


class ConsolidationResponse(BaseModel):
    """Response model for ingredient consolidation."""
    consolidated_grocery_list: ConsolidatedGroceryList
    consolidation_stats: Dict[str, Any]
    quality_metrics: Dict[str, float]


class ConsolidationStats(BaseModel):
    """Statistics about consolidation process."""
    original_ingredient_count: int
    consolidated_ingredient_count: int
    reduction_percentage: float
    groups_created: int
    failed_merges: int
    unit_conversions_performed: int
    fuzzy_matches_made: int


class IngredientConsolidatorAgent:
    """
    PydanticAI agent for consolidating ingredients with intelligent deduplication.

    Manages ingredient merging using fuzzy matching, unit conversion,
    and category-based organization with quality scoring.
    """

    def __init__(self):
        """Initialize ingredient consolidator agent."""
        self.settings = get_settings()
        self.consolidator = IngredientConsolidator()

        # Initialize PydanticAI agent with configurable model
        model_config = self.settings.get_llm_model_config()
        self.agent = Agent(
            model_config,
            deps_type=Dict[str, Any],
            retries=1  # Less retries since this is more deterministic
        )

        # Set up agent tools
        self._setup_agent_tools()

    def _get_dependencies(self) -> Dict[str, Any]:
        """Get agent dependencies."""
        return {
            'consolidator': self.consolidator,
            'settings': self.settings
        }

    def _setup_agent_tools(self) -> None:
        """Set up agent tools and handlers."""

        @self.agent.tool
        async def analyze_ingredient_similarity(
            ctx: RunContext[Dict[str, Any]],
            ingredients: List[Ingredient],
            threshold: float
        ) -> Dict[str, List[str]]:
            """Analyze ingredient similarity and return grouping suggestions."""
            try:
                # Use fuzzy matching to find similar ingredients
                from fuzzywuzzy import fuzz

                groups = defaultdict(list)
                processed = set()

                for i, ingredient in enumerate(ingredients):
                    if i in processed:
                        continue

                    group_key = ingredient.name
                    groups[group_key].append(ingredient.name)
                    processed.add(i)

                    # Find similar ingredients
                    for j, other_ingredient in enumerate(ingredients[i + 1:], start=i + 1):
                        if j in processed:
                            continue

                        similarity = fuzz.ratio(ingredient.name.lower(), other_ingredient.name.lower())
                        if similarity >= threshold:
                            groups[group_key].append(other_ingredient.name)
                            processed.add(j)

                result = {group: list(set(members)) for group, members in groups.items() if len(members) > 1}
                logger.info(f"Found {len(result)} similarity groups above threshold {threshold}")
                return result

            except Exception as e:
                logger.error(f"Failed to analyze ingredient similarity: {e}")
                raise

        @self.agent.tool
        async def validate_unit_compatibility(
            ctx: RunContext[Dict[str, Any]],
            ingredients: List[Ingredient]
        ) -> Dict[str, List[str]]:
            """Validate unit compatibility for consolidation."""
            try:
                compatibility_groups = {
                    'volume': ['cup', 'tablespoon', 'teaspoon', 'liter', 'milliliter', 'fluid_ounce', 'pint', 'quart', 'gallon'],
                    'weight': ['pound', 'ounce', 'gram', 'kilogram'],
                    'count': ['whole', 'piece', 'clove', 'bunch', 'package'],
                    'special': ['to_taste', 'pinch', 'dash']
                }

                unit_groups = defaultdict(list)

                for ingredient in ingredients:
                    unit_value = ingredient.unit.value
                    unit_group = 'other'

                    for group_name, units in compatibility_groups.items():
                        if unit_value in units:
                            unit_group = group_name
                            break

                    unit_groups[unit_group].append(f"{ingredient.name} ({unit_value})")

                result = {group: members for group, members in unit_groups.items() if members}
                logger.info(f"Unit compatibility analysis: {len(result)} unit groups found")
                return result

            except Exception as e:
                logger.error(f"Failed to validate unit compatibility: {e}")
                raise

        @self.agent.tool
        async def calculate_consolidation_quality(
            ctx: RunContext[Dict[str, Any]],
            original_ingredients: List[Ingredient],
            consolidated_list: ConsolidatedGroceryList
        ) -> Dict[str, float]:
            """Calculate quality metrics for consolidation results."""
            try:
                metrics = {}

                # Reduction ratio
                original_count = len(original_ingredients)
                consolidated_count = len(consolidated_list.ingredients)
                metrics['reduction_ratio'] = (original_count - consolidated_count) / original_count if original_count > 0 else 0

                # Average confidence score
                if consolidated_list.ingredients:
                    avg_confidence = sum(ing.confidence for ing in consolidated_list.ingredients) / len(consolidated_list.ingredients)
                    metrics['average_confidence'] = avg_confidence
                else:
                    metrics['average_confidence'] = 0.0

                # Category coverage
                categories = set(ing.category for ing in consolidated_list.ingredients if ing.category)
                metrics['category_coverage'] = len(categories) / len(IngredientCategory) if categories else 0

                # Unit distribution (prefer simpler units)
                unit_types = defaultdict(int)
                for ingredient in consolidated_list.ingredients:
                    unit_type = self._get_unit_type_for_metric(ingredient.unit)
                    unit_types[unit_type] += 1

                # Prefer volume > weight > count > special for readability
                preferred_order = {'volume': 0.4, 'weight': 0.3, 'count': 0.2, 'special': 0.1}
                unit_score = sum(
                    count * preferred_order.get(unit_type, 0.1)
                    for unit_type, count in unit_types.items()
                ) / consolidated_count if consolidated_count > 0 else 0

                metrics['unit_preference_score'] = unit_score

                logger.info(f"Quality metrics: {metrics}")
                return metrics

            except Exception as e:
                logger.error(f"Failed to calculate consolidation quality: {e}")
                return {'error': str(e)}

    def _get_unit_type_for_metric(self, unit: UnitEnum) -> str:
        """Get unit type for quality metrics."""
        volume_units = {
            UnitEnum.CUP, UnitEnum.TABLESPOON, UnitEnum.TEASPOON,
            UnitEnum.FLUID_OUNCE, UnitEnum.PINT, UnitEnum.QUART,
            UnitEnum.GALLON, UnitEnum.LITER, UnitEnum.MILLILITER
        }
        weight_units = {
            UnitEnum.POUND, UnitEnum.OUNCE, UnitEnum.GRAM, UnitEnum.KILOGRAM
        }
        count_units = {
            UnitEnum.WHOLE, UnitEnum.PIECE, UnitEnum.CLOVE,
            UnitEnum.BUNCH, UnitEnum.PACKAGE
        }

        if unit in volume_units:
            return "volume"
        elif unit in weight_units:
            return "weight"
        elif unit in count_units:
            return "count"
        else:
            return "special"

    async def consolidate_ingredients(self, request: ConsolidationRequest) -> ConsolidationResponse:
        """
        Consolidate ingredients using intelligent deduplication strategies.

        Args:
            request: Consolidation request with ingredients and parameters

        Returns:
            Consolidation response with results and metrics

        Raises:
            AgentError: If consolidation fails
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting consolidation of {len(request.ingredients)} ingredients")

        try:
            # Test mode bypass - use simple consolidation
            if self.settings.llm_model == "test":
                return self._create_simple_consolidation_for_test(request, start_time)

            # Pre-consolidation analysis
            similarity_analysis = await self.agent.run(
                "analyze_ingredient_similarity",
                ingredients=request.ingredients,
                threshold=request.similarity_threshold
            )

            unit_analysis = await self.agent.run(
                "validate_unit_compatibility",
                ingredients=request.ingredients
            )

            logger.info(f"Pre-analysis: {len(similarity_analysis.data)} similarity groups, {len(unit_analysis.data)} unit groups")

            # Perform consolidation
            consolidated_list = await self.consolidator.consolidate_ingredients(
                request.ingredients,
                request.serving_size
            )

            # Post-consolidation quality analysis
            quality_metrics = await self.agent.run(
                "calculate_consolidation_quality",
                original_ingredients=request.ingredients,
                consolidated_list=consolidated_list
            )

            # Calculate processing statistics
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            stats = self._calculate_consolidation_stats(
                request.ingredients,
                consolidated_list,
                similarity_analysis.data,
                processing_time
            )

            response = ConsolidationResponse(
                consolidated_grocery_list=consolidated_list,
                consolidation_stats=stats,
                quality_metrics=quality_metrics.data
            )

            logger.info(f"Consolidation complete: {stats['original_ingredient_count']} → {stats['consolidated_ingredient_count']} ingredients ({stats['reduction_percentage']:.1f}% reduction)")
            return response

        except IngredientConsolidationError as e:
            raise AgentError(
                f"Ingredient consolidation failed: {e.message}",
                agent_name="ingredient_consolidator",
                agent_task="consolidate_ingredients",
                details={
                    'ingredient_count': len(request.ingredients),
                    'consolidation_error': e.details
                }
            )

        except Exception as e:
            raise AgentError(
                f"Consolidation agent error: {str(e)}",
                agent_name="ingredient_consolidator",
                agent_task="consolidate_ingredients",
                details={
                    'ingredient_count': len(request.ingredients),
                    'processing_time_ms': int((datetime.utcnow() - start_time).total_seconds() * 1000)
                }
            )

    def _calculate_consolidation_stats(
        self,
        original_ingredients: List[Ingredient],
        consolidated_list: ConsolidatedGroceryList,
        similarity_groups: Dict[str, List[str]],
        processing_time_ms: float
    ) -> Dict[str, Any]:
        """Calculate detailed consolidation statistics."""

        original_count = len(original_ingredients)
        consolidated_count = len(consolidated_list.ingredients)
        reduction_percentage = ((original_count - consolidated_count) / original_count * 100) if original_count > 0 else 0

        # Count different types of operations
        unit_conversions = len([note for note in consolidated_list.consolidation_notes if 'converted' in note.lower()])
        fuzzy_matches = len(similarity_groups)
        failed_merges = len([note for note in consolidated_list.consolidation_notes if 'failed' in note.lower()])

        return {
            'original_ingredient_count': original_count,
            'consolidated_ingredient_count': consolidated_count,
            'reduction_percentage': reduction_percentage,
            'groups_created': fuzzy_matches,
            'failed_merges': failed_merges,
            'unit_conversions_performed': unit_conversions,
            'fuzzy_matches_made': fuzzy_matches,
            'processing_time_ms': int(processing_time_ms),
            'notes_generated': len(consolidated_list.consolidation_notes)
        }

    async def analyze_ingredient_conflicts(self, ingredients: List[Ingredient]) -> Dict[str, Any]:
        """
        Analyze potential conflicts in ingredient consolidation.

        Args:
            ingredients: List of ingredients to analyze

        Returns:
            Conflict analysis report
        """
        try:
            conflicts = {
                'unit_conflicts': [],
                'category_conflicts': [],
                'confidence_warnings': [],
                'merge_challenges': []
            }

            # Group ingredients by similar names
            name_groups = defaultdict(list)
            for ingredient in ingredients:
                name_key = ingredient.name.lower().strip()
                name_groups[name_key].append(ingredient)

            # Analyze each group
            for name, group_ingredients in name_groups.items():
                if len(group_ingredients) > 1:
                    # Check for unit conflicts
                    units = set(ing.unit for ing in group_ingredients)
                    if len(units) > 1:
                        unit_types = set(self._get_unit_type_for_metric(unit) for unit in units)
                        if len(unit_types) > 1:
                            conflicts['unit_conflicts'].append({
                                'ingredient_name': name,
                                'conflicting_units': [unit.value for unit in units],
                                'unit_types': list(unit_types)
                            })

                    # Check for category conflicts
                    categories = set(ing.category for ing in group_ingredients if ing.category)
                    if len(categories) > 1:
                        conflicts['category_conflicts'].append({
                            'ingredient_name': name,
                            'conflicting_categories': [cat.value for cat in categories]
                        })

                    # Check for low confidence ingredients
                    low_confidence = [ing for ing in group_ingredients if ing.confidence < 0.6]
                    if low_confidence:
                        conflicts['confidence_warnings'].append({
                            'ingredient_name': name,
                            'low_confidence_count': len(low_confidence),
                            'min_confidence': min(ing.confidence for ing in low_confidence),
                            'examples': [ing.original_text for ing in low_confidence[:2]]
                        })

            return conflicts

        except Exception as e:
            logger.error(f"Failed to analyze ingredient conflicts: {e}")
            return {'error': str(e)}

    async def suggest_consolidation_improvements(
        self,
        consolidated_list: ConsolidatedGroceryList,
        quality_metrics: Dict[str, float]
    ) -> List[str]:
        """
        Suggest improvements to consolidation results.

        Args:
            consolidated_list: Consolidated grocery list
            quality_metrics: Quality metrics from consolidation

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        try:
            # Analyze quality metrics for suggestions
            reduction_ratio = quality_metrics.get('reduction_ratio', 0)
            average_confidence = quality_metrics.get('average_confidence', 0)
            unit_preference_score = quality_metrics.get('unit_preference_score', 0)

            # Reduction ratio suggestions
            if reduction_ratio < 0.2:
                suggestions.append("Consider lowering similarity threshold to merge more ingredients")
            elif reduction_ratio > 0.6:
                suggestions.append("High reduction ratio - verify that merged ingredients are actually similar")

            # Confidence suggestions
            if average_confidence < 0.7:
                suggestions.append("Low average confidence - consider reviewing ingredient extraction quality")
            elif average_confidence < 0.8:
                suggestions.append("Some ingredients have medium confidence - manual review recommended")

            # Unit preference suggestions
            if unit_preference_score < 0.3:
                suggestions.append("Consider converting more ingredients to volume measurements for easier shopping")

            # Analyze specific patterns in consolidated list
            unit_distribution = defaultdict(int)
            category_distribution = defaultdict(int)

            for ingredient in consolidated_list.ingredients:
                unit_distribution[self._get_unit_type_for_metric(ingredient.unit)] += 1
                if ingredient.category:
                    category_distribution[ingredient.category] += 1

            # Unit distribution suggestions
            if unit_distribution.get('special', 0) > len(consolidated_list.ingredients) * 0.3:
                suggestions.append("Many ingredients use 'to taste' or similar units - consider providing quantity ranges")

            # Category distribution suggestions
            if len(category_distribution) < 4:
                suggestions.append("Limited ingredient categories - consider improving category classification")

            # Consolidation notes analysis
            conversion_notes = [note for note in consolidated_list.consolidation_notes if 'converted' in note.lower()]
            if len(conversion_notes) > len(consolidated_list.ingredients) * 0.5:
                suggestions.append("Many unit conversions performed - verify converted quantities are accurate")

            if not suggestions:
                suggestions.append("Consolidation quality looks good - no major improvements suggested")

            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate consolidation suggestions: {e}")
            return [f"Error generating suggestions: {str(e)}"]


    def _create_simple_consolidation_for_test(self, request: ConsolidationRequest, start_time: datetime) -> ConsolidationResponse:
        """Create simple consolidation for test mode."""
        from core.models import ConsolidatedGroceryList, Ingredient

        # Simple consolidation - just group similar ingredients by name
        consolidated_ingredients = []
        consolidation_notes = []

        # Group ingredients by similar names
        ingredient_groups = {}
        for ingredient in request.ingredients:
            # Simple grouping by base name (lowercase, remove plurals)
            base_name = ingredient.name.lower().rstrip('s')
            if base_name not in ingredient_groups:
                ingredient_groups[base_name] = []
            ingredient_groups[base_name].append(ingredient)

        # Consolidate each group
        for base_name, ingredients in ingredient_groups.items():
            if len(ingredients) == 1:
                # Single ingredient - just add it
                consolidated_ingredients.append(ingredients[0])
            else:
                # Multiple ingredients - merge them
                primary = ingredients[0]
                total_quantity = sum(ing.quantity for ing in ingredients)

                merged_ingredient = Ingredient(
                    name=primary.name,
                    quantity=total_quantity,
                    unit=primary.unit,
                    category=primary.category,
                    confidence=sum(ing.confidence for ing in ingredients) / len(ingredients),
                    original_text=f"Merged from {len(ingredients)} ingredients"
                )

                consolidated_ingredients.append(merged_ingredient)
                consolidation_notes.append(f"Merged {len(ingredients)} {base_name} ingredients")

        # Create consolidated grocery list
        grocery_list = ConsolidatedGroceryList(
            ingredients=consolidated_ingredients,
            total_items=len(consolidated_ingredients),
            consolidation_notes=consolidation_notes,
            serving_size=request.serving_size,
            generated_at=datetime.utcnow()
        )

        # Create response
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        consolidation_stats = {
            'original_count': len(request.ingredients),
            'consolidated_count': len(consolidated_ingredients),
            'consolidation_ratio': len(consolidated_ingredients) / len(request.ingredients) if request.ingredients else 0,
            'processing_time_ms': processing_time_ms
        }

        quality_metrics = {
            'similarity_score': 0.8,
            'unit_consistency_score': 0.9,
            'category_coverage_score': 0.85
        }

        return ConsolidationResponse(
            consolidated_grocery_list=grocery_list,
            consolidation_stats=consolidation_stats,
            quality_metrics=quality_metrics
        )


# Convenience functions for external usage

async def consolidate_ingredients(
    ingredients: List[Ingredient],
    serving_size: int = 8,
    similarity_threshold: float = 85.0
) -> ConsolidationResponse:
    """
    Consolidate ingredients using intelligent deduplication.

    Args:
        ingredients: List of ingredients to consolidate
        serving_size: Target serving size
        similarity_threshold: Fuzzy matching threshold (0-100)

    Returns:
        Consolidation response with results and metrics
    """
    agent = IngredientConsolidatorAgent()
    request = ConsolidationRequest(
        ingredients=ingredients,
        serving_size=serving_size,
        similarity_threshold=similarity_threshold
    )
    return await agent.consolidate_ingredients(request)


async def analyze_consolidation_quality(
    original_ingredients: List[Ingredient],
    consolidated_list: ConsolidatedGroceryList
) -> Dict[str, float]:
    """
    Analyze quality of ingredient consolidation.

    Args:
        original_ingredients: Original ingredient list
        consolidated_list: Consolidated grocery list

    Returns:
        Quality metrics dictionary
    """
    agent = IngredientConsolidatorAgent()
    quality_result = await agent.agent.run(
        "calculate_consolidation_quality",
        original_ingredients=original_ingredients,
        consolidated_list=consolidated_list
    )
    return quality_result.data