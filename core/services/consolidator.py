"""
Ingredient consolidator for Holiday Meal Planner.

Implements fuzzy matching, unit conversion, and quantity aggregation
to consolidate duplicate ingredients from multiple recipes.
"""

import logging
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

from fuzzywuzzy import fuzz
from pint import UnitRegistry
from pint.errors import UndefinedUnitError, DimensionalityError

from core.models import Ingredient, UnitEnum, ConsolidatedGroceryList, IngredientCategory
from shared.exceptions import IngredientConsolidationError
from shared.config import get_settings


logger = logging.getLogger(__name__)


class IngredientConsolidator:
    """
    Service for consolidating ingredients with fuzzy matching and unit conversion.

    Handles deduplication, unit normalization, and quantity aggregation
    across ingredients from multiple recipes.
    """

    def __init__(self):
        """Initialize consolidator with unit registry and matching rules."""
        self.settings = get_settings()
        self._setup_unit_registry()
        self._setup_fuzzy_matching()
        self._setup_density_table()

    def _setup_unit_registry(self) -> None:
        """Set up pint unit registry for unit conversions."""
        self.ureg = UnitRegistry()

        # Define custom units and relationships
        self._define_custom_units()

    def _define_custom_units(self) -> None:
        """Define custom units and cooking-specific conversions."""
        # Add cooking-specific units if not defined
        try:
            # Define pinch and dash as very small amounts
            self.ureg.define('pinch = 1/8 * teaspoon')
            self.ureg.define('dash = 1/16 * teaspoon')

            # Define package as a count unit (will be handled specially)
            self.ureg.define('package = 1 * dimensionless')
            self.ureg.define('bunch = 1 * dimensionless')
            self.ureg.define('clove = 1 * dimensionless')

        except Exception as e:
            logger.warning(f"Failed to define custom units: {e}")

    def _setup_fuzzy_matching(self) -> None:
        """Set up fuzzy matching parameters and synonym mappings."""
        self.fuzzy_threshold = 85  # Minimum similarity score for matching
        self.fuzzy_threshold_high = 95  # High confidence threshold

        # Synonym mappings for common ingredient variations
        self.synonyms = {
            # Common ingredient variations
            "all-purpose flour": ["flour", "ap flour", "white flour", "plain flour"],
            "olive oil": ["extra virgin olive oil", "evoo", "olive oil extra virgin"],
            "butter": ["unsalted butter", "salted butter", "sweet butter"],
            "onion": ["yellow onion", "white onion", "spanish onion"],
            "garlic": ["garlic cloves", "fresh garlic"],
            "black pepper": ["pepper", "ground black pepper", "fresh ground pepper"],
            "kosher salt": ["salt", "table salt", "sea salt"],
            "chicken broth": ["chicken stock", "chicken bouillon"],
            "vegetable oil": ["canola oil", "neutral oil", "cooking oil"],
            "heavy cream": ["heavy whipping cream", "whipping cream", "double cream"],
            "parmesan cheese": ["parmigiano-reggiano", "parmesan", "grated parmesan"],
            "tomatoes": ["canned tomatoes", "diced tomatoes", "crushed tomatoes"],

            # Herb variations
            "fresh basil": ["basil", "sweet basil"],
            "fresh parsley": ["parsley", "flat-leaf parsley", "italian parsley"],
            "fresh thyme": ["thyme", "thyme leaves"],

            # Protein variations
            "chicken breast": ["boneless chicken breast", "chicken breast fillets"],
            "ground beef": ["ground chuck", "hamburger meat", "minced beef"],
        }

        # Create reverse mapping
        self.canonical_names = {}
        for canonical, variations in self.synonyms.items():
            self.canonical_names[canonical] = canonical
            for variation in variations:
                self.canonical_names[variation] = canonical

    def _setup_density_table(self) -> None:
        """Set up density table for volume-to-weight conversions."""
        # Approximate densities for common ingredients (grams per cup)
        self.ingredient_densities = {
            # Dry ingredients
            "flour": 125,
            "sugar": 200,
            "brown sugar": 213,
            "powdered sugar": 120,
            "butter": 227,
            "oil": 218,
            "honey": 340,
            "oats": 80,
            "rice": 185,
            "breadcrumbs": 108,
            "cocoa powder": 75,
            "baking powder": 192,
            "baking soda": 192,
            "salt": 292,

            # Nuts and seeds
            "almonds": 143,
            "walnuts": 120,
            "pecans": 120,

            # Dairy
            "milk": 244,
            "cream": 232,
            "sour cream": 240,
            "yogurt": 245,
            "cheese": 113,  # grated cheese

            # Vegetables (when chopped)
            "onion": 160,
            "carrot": 128,
            "celery": 120,
            "potato": 150,
            "tomato": 180,

            # Fruits
            "apple": 125,
            "banana": 150,

            # Liquids (all approximately 237ml/cup = 237g/cup for water-like)
            "water": 237,
            "broth": 237,
            "juice": 237,
        }

    async def consolidate_ingredients(
        self,
        ingredients: List[Ingredient],
        serving_size: int = 8
    ) -> ConsolidatedGroceryList:
        """
        Consolidate a list of ingredients into a unified grocery list.

        Args:
            ingredients: List of ingredients to consolidate
            serving_size: Target serving size for the consolidated list

        Returns:
            ConsolidatedGroceryList with merged ingredients

        Raises:
            IngredientConsolidationError: If consolidation fails
        """
        if not ingredients:
            raise IngredientConsolidationError(
                "Cannot consolidate empty ingredients list",
                consolidation_step="input_validation"
            )

        logger.info(f"Consolidating {len(ingredients)} ingredients")

        try:
            # Step 1: Normalize ingredient names
            normalized_ingredients = await self._normalize_ingredient_names(ingredients)

            # Step 2: Group similar ingredients
            ingredient_groups = await self._group_similar_ingredients(normalized_ingredients)

            # Step 3: Merge ingredients within each group
            consolidated_ingredients = []
            consolidation_notes = []

            for group_name, group_ingredients in ingredient_groups.items():
                try:
                    merged_ingredient, merge_notes = await self._merge_ingredient_group(
                        group_ingredients, group_name
                    )
                    consolidated_ingredients.append(merged_ingredient)
                    consolidation_notes.extend(merge_notes)

                except Exception as e:
                    logger.warning(f"Failed to merge group '{group_name}': {e}")
                    # Add ingredients individually if merging fails
                    for ingredient in group_ingredients:
                        consolidated_ingredients.append(ingredient)
                    consolidation_notes.append(f"Failed to merge group '{group_name}': {str(e)}")

            # Step 4: Sort ingredients by category and name
            sorted_ingredients = self._sort_consolidated_ingredients(consolidated_ingredients)

            # Step 5: Create consolidated grocery list
            grocery_list = ConsolidatedGroceryList(
                ingredients=sorted_ingredients,
                total_items=len(sorted_ingredients),
                consolidation_notes=consolidation_notes,
                serving_size=serving_size
            )

            logger.info(f"Consolidated to {len(sorted_ingredients)} unique ingredients")
            return grocery_list

        except Exception as e:
            raise IngredientConsolidationError(
                f"Consolidation failed: {str(e)}",
                consolidation_step="main_process",
                details={"original_count": len(ingredients)}
            )

    async def _normalize_ingredient_names(self, ingredients: List[Ingredient]) -> List[Ingredient]:
        """
        Normalize ingredient names using canonical mappings.

        Args:
            ingredients: List of ingredients to normalize

        Returns:
            List of ingredients with normalized names
        """
        normalized = []

        for ingredient in ingredients:
            name = ingredient.name.lower().strip()

            # Check for canonical name
            canonical_name = self.canonical_names.get(name, name)

            # Create new ingredient with canonical name
            normalized_ingredient = Ingredient(
                name=canonical_name,
                quantity=ingredient.quantity,
                unit=ingredient.unit,
                category=ingredient.category,
                confidence=ingredient.confidence,
                original_text=ingredient.original_text
            )

            normalized.append(normalized_ingredient)

        return normalized

    async def _group_similar_ingredients(self, ingredients: List[Ingredient]) -> Dict[str, List[Ingredient]]:
        """
        Group similar ingredients together using fuzzy matching.

        Args:
            ingredients: List of normalized ingredients

        Returns:
            Dictionary mapping group names to lists of similar ingredients
        """
        groups = defaultdict(list)
        processed_names = set()

        for ingredient in ingredients:
            name = ingredient.name
            group_found = False

            # Check if this ingredient should be grouped with existing groups
            for group_name in groups.keys():
                if group_name in processed_names:
                    continue

                similarity = fuzz.ratio(name, group_name)

                if similarity >= self.fuzzy_threshold:
                    groups[group_name].append(ingredient)
                    group_found = True
                    break

            # If no similar group found, create new group
            if not group_found:
                groups[name].append(ingredient)
                processed_names.add(name)

        return dict(groups)

    async def _merge_ingredient_group(
        self,
        ingredients: List[Ingredient],
        group_name: str
    ) -> Tuple[Ingredient, List[str]]:
        """
        Merge a group of similar ingredients into a single ingredient.

        Args:
            ingredients: List of ingredients in the group
            group_name: Name of the ingredient group

        Returns:
            Tuple of (merged_ingredient, merge_notes)
        """
        if len(ingredients) == 1:
            return ingredients[0], []

        notes = []
        notes.append(f"Merged {len(ingredients)} instances of '{group_name}'")

        try:
            # Choose the best name (highest confidence or most common)
            best_name = self._choose_best_name(ingredients, group_name)

            # Choose the best category
            best_category = self._choose_best_category(ingredients)

            # Convert all to common unit and sum quantities
            total_quantity, common_unit, conversion_notes = await self._sum_quantities(ingredients)
            notes.extend(conversion_notes)

            # Calculate average confidence
            avg_confidence = sum(ing.confidence for ing in ingredients) / len(ingredients)

            # Combine original texts
            original_texts = [ing.original_text for ing in ingredients if ing.original_text]
            combined_original = "; ".join(original_texts[:3])  # Limit to first 3
            if len(original_texts) > 3:
                combined_original += f" (and {len(original_texts) - 3} more)"

            # Create merged ingredient
            merged_ingredient = Ingredient(
                name=best_name,
                quantity=total_quantity,
                unit=common_unit,
                category=best_category,
                confidence=avg_confidence,
                original_text=combined_original
            )

            return merged_ingredient, notes

        except Exception as e:
            raise IngredientConsolidationError(
                f"Failed to merge ingredient group: {str(e)}",
                ingredient_names=[ing.name for ing in ingredients],
                consolidation_step="group_merge",
                details={"group_name": group_name, "ingredient_count": len(ingredients)}
            )

    def _choose_best_name(self, ingredients: List[Ingredient], group_name: str) -> str:
        """Choose the best name from a group of ingredients."""
        # Count frequency of each name
        name_counts = defaultdict(int)
        name_confidences = defaultdict(list)

        for ingredient in ingredients:
            name = ingredient.name
            name_counts[name] += 1
            name_confidences[name].append(ingredient.confidence)

        # Calculate weighted score (frequency * average confidence)
        best_name = group_name
        best_score = 0

        for name, count in name_counts.items():
            avg_confidence = sum(name_confidences[name]) / len(name_confidences[name])
            score = count * avg_confidence

            if score > best_score:
                best_score = score
                best_name = name

        return best_name

    def _choose_best_category(self, ingredients: List[Ingredient]) -> Optional[IngredientCategory]:
        """Choose the best category from a group of ingredients."""
        # Count categories, ignoring None and OTHER
        category_counts = defaultdict(int)

        for ingredient in ingredients:
            if ingredient.category and ingredient.category != IngredientCategory.OTHER:
                category_counts[ingredient.category] += 1

        if not category_counts:
            return IngredientCategory.OTHER

        # Return most common category
        return max(category_counts, key=category_counts.get)

    async def _sum_quantities(self, ingredients: List[Ingredient]) -> Tuple[float, UnitEnum, List[str]]:
        """
        Sum quantities of ingredients, converting units as needed.

        Args:
            ingredients: List of ingredients to sum

        Returns:
            Tuple of (total_quantity, common_unit, conversion_notes)
        """
        if len(ingredients) == 1:
            ing = ingredients[0]
            return ing.quantity, ing.unit, []

        notes = []

        # Group ingredients by unit type
        volume_ingredients = []
        weight_ingredients = []
        count_ingredients = []
        special_ingredients = []

        for ingredient in ingredients:
            unit_type = self._get_unit_type(ingredient.unit)
            if unit_type == "volume":
                volume_ingredients.append(ingredient)
            elif unit_type == "weight":
                weight_ingredients.append(ingredient)
            elif unit_type == "count":
                count_ingredients.append(ingredient)
            else:
                special_ingredients.append(ingredient)

        # Try to consolidate the largest group
        largest_group = max(
            [volume_ingredients, weight_ingredients, count_ingredients, special_ingredients],
            key=len
        )

        if not largest_group:
            # Fallback: just sum first ingredients
            total_quantity = sum(ing.quantity for ing in ingredients)
            return total_quantity, ingredients[0].unit, notes

        # Determine target unit
        if largest_group == volume_ingredients:
            target_unit, total_quantity, conversion_notes = await self._sum_volume_ingredients(ingredients)
        elif largest_group == weight_ingredients:
            target_unit, total_quantity, conversion_notes = await self._sum_weight_ingredients(ingredients)
        elif largest_group == count_ingredients:
            target_unit, total_quantity, conversion_notes = await self._sum_count_ingredients(ingredients)
        else:
            target_unit, total_quantity, conversion_notes = await self._sum_special_ingredients(ingredients)

        notes.extend(conversion_notes)
        return total_quantity, target_unit, notes

    def _get_unit_type(self, unit: UnitEnum) -> str:
        """Get the type category of a unit."""
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

    async def _sum_volume_ingredients(self, ingredients: List[Ingredient]) -> Tuple[UnitEnum, float, List[str]]:
        """Sum ingredients with volume units."""
        total_ml = 0.0
        notes = []

        for ingredient in ingredients:
            unit_type = self._get_unit_type(ingredient.unit)

            if unit_type == "volume":
                # Convert to milliliters
                ml = self._convert_to_ml(ingredient.quantity, ingredient.unit)
                total_ml += ml
            elif unit_type == "weight":
                # Try to convert weight to volume using density
                ml = await self._convert_weight_to_volume(ingredient)
                if ml:
                    total_ml += ml
                    notes.append(f"Converted {ingredient.name} from weight to volume using estimated density")
                else:
                    # Can't convert, add as-is (not ideal but better than losing data)
                    notes.append(f"Could not convert {ingredient.name} from weight units - kept original measurement")
                    return ingredient.unit, ingredient.quantity, notes
            else:
                # Count or special units - can't easily convert
                notes.append(f"Could not convert {ingredient.name} with {ingredient.unit.value} units")
                return ingredient.unit, ingredient.quantity, notes

        # Convert back to best volume unit
        target_unit, final_quantity = self._ml_to_best_unit(total_ml)
        return target_unit, final_quantity, notes

    async def _sum_weight_ingredients(self, ingredients: List[Ingredient]) -> Tuple[UnitEnum, float, List[str]]:
        """Sum ingredients with weight units."""
        total_grams = 0.0
        notes = []

        for ingredient in ingredients:
            unit_type = self._get_unit_type(ingredient.unit)

            if unit_type == "weight":
                # Convert to grams
                grams = self._convert_to_grams(ingredient.quantity, ingredient.unit)
                total_grams += grams
            elif unit_type == "volume":
                # Try to convert volume to weight using density
                grams = await self._convert_volume_to_weight(ingredient)
                if grams:
                    total_grams += grams
                    notes.append(f"Converted {ingredient.name} from volume to weight using estimated density")
                else:
                    notes.append(f"Could not convert {ingredient.name} from volume units - kept original measurement")
                    return ingredient.unit, ingredient.quantity, notes
            else:
                notes.append(f"Could not convert {ingredient.name} with {ingredient.unit.value} units")
                return ingredient.unit, ingredient.quantity, notes

        # Convert back to best weight unit
        target_unit, final_quantity = self._grams_to_best_unit(total_grams)
        return target_unit, final_quantity, notes

    async def _sum_count_ingredients(self, ingredients: List[Ingredient]) -> Tuple[UnitEnum, float, List[str]]:
        """Sum ingredients with count units."""
        total_count = sum(ing.quantity for ing in ingredients if self._get_unit_type(ing.unit) == "count")
        notes = []

        # Use the most common count unit
        count_units = [ing.unit for ing in ingredients if self._get_unit_type(ing.unit) == "count"]
        if count_units:
            most_common_unit = max(set(count_units), key=count_units.count)
        else:
            most_common_unit = UnitEnum.WHOLE

        # Note if we had to skip non-count ingredients
        non_count = [ing for ing in ingredients if self._get_unit_type(ing.unit) != "count"]
        if non_count:
            notes.append(f"Skipped {len(non_count)} ingredients with non-count units")

        return most_common_unit, total_count, notes

    async def _sum_special_ingredients(self, ingredients: List[Ingredient]) -> Tuple[UnitEnum, float, List[str]]:
        """Sum ingredients with special units like 'to taste'."""
        # For special units, just use the first one
        first_ingredient = ingredients[0]
        notes = [f"Used first measurement for special unit ingredients"]

        return first_ingredient.unit, first_ingredient.quantity, notes

    def _convert_to_ml(self, quantity: float, unit: UnitEnum) -> float:
        """Convert volume quantity to milliliters."""
        try:
            # Map our units to pint units
            unit_mapping = {
                UnitEnum.CUP: "cup",
                UnitEnum.TABLESPOON: "tablespoon",
                UnitEnum.TEASPOON: "teaspoon",
                UnitEnum.FLUID_OUNCE: "fluid_ounce",
                UnitEnum.PINT: "pint",
                UnitEnum.QUART: "quart",
                UnitEnum.GALLON: "gallon",
                UnitEnum.LITER: "liter",
                UnitEnum.MILLILITER: "milliliter",
                UnitEnum.PINCH: "pinch",
                UnitEnum.DASH: "dash",
            }

            pint_unit = unit_mapping.get(unit)
            if not pint_unit:
                return quantity  # Return as-is if can't convert

            # Use pint for conversion
            pint_quantity = quantity * self.ureg(pint_unit)
            ml_quantity = pint_quantity.to('milliliter').magnitude

            return ml_quantity

        except Exception:
            # Fallback conversions
            fallback_conversions = {
                UnitEnum.CUP: 237,
                UnitEnum.TABLESPOON: 14.8,
                UnitEnum.TEASPOON: 4.93,
                UnitEnum.FLUID_OUNCE: 29.57,
                UnitEnum.PINT: 473,
                UnitEnum.QUART: 946,
                UnitEnum.GALLON: 3785,
                UnitEnum.LITER: 1000,
                UnitEnum.MILLILITER: 1,
                UnitEnum.PINCH: 0.62,  # 1/8 tsp
                UnitEnum.DASH: 0.31,   # 1/16 tsp
            }

            multiplier = fallback_conversions.get(unit, 1)
            return quantity * multiplier

    def _convert_to_grams(self, quantity: float, unit: UnitEnum) -> float:
        """Convert weight quantity to grams."""
        try:
            unit_mapping = {
                UnitEnum.POUND: "pound",
                UnitEnum.OUNCE: "ounce",
                UnitEnum.GRAM: "gram",
                UnitEnum.KILOGRAM: "kilogram",
            }

            pint_unit = unit_mapping.get(unit)
            if not pint_unit:
                return quantity

            pint_quantity = quantity * self.ureg(pint_unit)
            gram_quantity = pint_quantity.to('gram').magnitude

            return gram_quantity

        except Exception:
            # Fallback conversions
            fallback_conversions = {
                UnitEnum.POUND: 453.6,
                UnitEnum.OUNCE: 28.35,
                UnitEnum.GRAM: 1,
                UnitEnum.KILOGRAM: 1000,
            }

            multiplier = fallback_conversions.get(unit, 1)
            return quantity * multiplier

    async def _convert_weight_to_volume(self, ingredient: Ingredient) -> Optional[float]:
        """Convert weight ingredient to volume using density table."""
        name = ingredient.name.lower()

        # Find matching density
        density_g_per_cup = None
        for ingredient_key, density in self.ingredient_densities.items():
            if ingredient_key in name:
                density_g_per_cup = density
                break

        if not density_g_per_cup:
            return None

        # Convert ingredient weight to grams
        grams = self._convert_to_grams(ingredient.quantity, ingredient.unit)

        # Convert grams to cups using density
        cups = grams / density_g_per_cup

        # Convert cups to ml
        ml = cups * 237  # 1 cup = 237ml

        return ml

    async def _convert_volume_to_weight(self, ingredient: Ingredient) -> Optional[float]:
        """Convert volume ingredient to weight using density table."""
        name = ingredient.name.lower()

        # Find matching density
        density_g_per_cup = None
        for ingredient_key, density in self.ingredient_densities.items():
            if ingredient_key in name:
                density_g_per_cup = density
                break

        if not density_g_per_cup:
            return None

        # Convert ingredient volume to ml
        ml = self._convert_to_ml(ingredient.quantity, ingredient.unit)

        # Convert ml to cups
        cups = ml / 237  # 1 cup = 237ml

        # Convert cups to grams using density
        grams = cups * density_g_per_cup

        return grams

    def _ml_to_best_unit(self, ml: float) -> Tuple[UnitEnum, float]:
        """Convert milliliters to best display unit."""
        if ml >= 3785:  # >= 1 gallon
            return UnitEnum.GALLON, ml / 3785
        elif ml >= 946:  # >= 1 quart
            return UnitEnum.QUART, ml / 946
        elif ml >= 473:  # >= 1 pint
            return UnitEnum.PINT, ml / 473
        elif ml >= 237:  # >= 1 cup
            return UnitEnum.CUP, ml / 237
        elif ml >= 15:  # >= 1 tablespoon
            return UnitEnum.TABLESPOON, ml / 14.8
        elif ml >= 5:  # >= 1 teaspoon
            return UnitEnum.TEASPOON, ml / 4.93
        else:
            return UnitEnum.MILLILITER, ml

    def _grams_to_best_unit(self, grams: float) -> Tuple[UnitEnum, float]:
        """Convert grams to best display unit."""
        if grams >= 453.6:  # >= 1 pound
            return UnitEnum.POUND, grams / 453.6
        elif grams >= 28.35:  # >= 1 ounce
            return UnitEnum.OUNCE, grams / 28.35
        else:
            return UnitEnum.GRAM, grams

    def _sort_consolidated_ingredients(self, ingredients: List[Ingredient]) -> List[Ingredient]:
        """Sort consolidated ingredients by category and name."""
        # Define category order for display
        category_order = {
            IngredientCategory.PROTEIN: 0,
            IngredientCategory.VEGETABLE: 1,
            IngredientCategory.FRUIT: 2,
            IngredientCategory.DAIRY: 3,
            IngredientCategory.GRAIN: 4,
            IngredientCategory.FAT: 5,
            IngredientCategory.HERB: 6,
            IngredientCategory.SPICE: 7,
            IngredientCategory.OTHER: 8,
            None: 9
        }

        def sort_key(ingredient: Ingredient):
            category_rank = category_order.get(ingredient.category, 9)
            return (category_rank, ingredient.name.lower())

        return sorted(ingredients, key=sort_key)


# Convenience function for external usage
async def consolidate_ingredients(
    ingredients: List[Ingredient],
    serving_size: int = 8
) -> ConsolidatedGroceryList:
    """
    Consolidate a list of ingredients into a unified grocery list.

    Convenience function that creates an IngredientConsolidator instance
    and consolidates the ingredients.

    Args:
        ingredients: List of ingredients to consolidate
        serving_size: Target serving size for the consolidated list

    Returns:
        ConsolidatedGroceryList with merged ingredients

    Raises:
        IngredientConsolidationError: If consolidation fails
    """
    consolidator = IngredientConsolidator()
    return await consolidator.consolidate_ingredients(ingredients, serving_size)