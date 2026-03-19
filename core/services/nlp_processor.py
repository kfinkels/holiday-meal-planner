"""
NLP ingredient processor for Holiday Meal Planner.

Implements spaCy-based ingredient extraction with custom NER training,
confidence scoring, and robust parsing of natural language ingredient descriptions.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from fractions import Fraction

import spacy
from spacy.lang.en import English
from spacy.pipeline import EntityRuler
from spacy.tokens import Doc, Span

from core.models import Ingredient, UnitEnum, IngredientCategory
from shared.exceptions import RecipeParsingError, ValidationError
from shared.config import get_settings


logger = logging.getLogger(__name__)


class IngredientNLPProcessor:
    """
    NLP processor for extracting structured ingredient data from text.

    Uses spaCy with custom patterns and rules to parse ingredient strings
    into structured Ingredient objects with confidence scoring.
    """

    def __init__(self):
        """Initialize NLP processor with models and patterns."""
        self.settings = get_settings()
        self._setup_nlp()
        self._setup_patterns()

    def _setup_nlp(self) -> None:
        """Set up spaCy NLP pipeline."""
        try:
            # Try to load full English model
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("en_core_web_sm not found, using basic English model")
            # Fallback to basic English model
            self.nlp = English()
            self.nlp.add_pipe("sentencizer")

        # Add custom entity ruler for ingredients
        if "entity_ruler" not in self.nlp.pipe_names:
            ruler = self.nlp.add_pipe("entity_ruler", before="ner")
            self.entity_ruler = ruler
        else:
            self.entity_ruler = self.nlp.get_pipe("entity_ruler")

    def _setup_patterns(self) -> None:
        """Set up custom patterns for ingredient recognition."""
        # Unit patterns
        unit_patterns = []
        for unit in UnitEnum:
            unit_patterns.extend([
                {"label": "UNIT", "pattern": unit.value},
                {"label": "UNIT", "pattern": unit.value + "s"},  # plural
                {"label": "UNIT", "pattern": unit.value.replace("_", " ")},  # space version
            ])

        # Add common unit abbreviations
        unit_abbreviations = {
            "cup": ["c", "cups"],
            "tablespoon": ["tbsp", "tbs", "T", "tablespoons"],
            "teaspoon": ["tsp", "t", "teaspoons"],
            "pound": ["lb", "lbs", "pounds"],
            "ounce": ["oz", "ozs", "ounces"],
            "gram": ["g", "grams"],
            "kilogram": ["kg", "kgs", "kilograms"],
            "liter": ["l", "L", "liters"],
            "milliliter": ["ml", "mL", "milliliters"],
            "piece": ["pc", "pcs", "pieces"],
            "clove": ["cloves"],
            "bunch": ["bunches"],
            "package": ["pkg", "pkgs", "packages", "pack", "packs"],
            "pinch": ["pinches"],
            "dash": ["dashes"],
        }

        for unit, abbrevs in unit_abbreviations.items():
            for abbrev in abbrevs:
                unit_patterns.append({"label": "UNIT", "pattern": abbrev})

        # Quantity patterns (numbers and fractions)
        quantity_patterns = [
            {"label": "QUANTITY", "pattern": [{"IS_DIGIT": True}]},
            {"label": "QUANTITY", "pattern": [{"TEXT": {"REGEX": r"^\d+\/\d+$"}}]},  # fractions
            {"label": "QUANTITY", "pattern": [{"TEXT": {"REGEX": r"^\d+\.\d+$"}}]},  # decimals
            {"label": "QUANTITY", "pattern": [{"LOWER": {"IN": ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]}}]},
            {"label": "QUANTITY", "pattern": [{"LOWER": {"IN": ["a", "an"]}}]},  # "a cup", "an onion"
        ]

        # Common ingredient words to help with recognition
        ingredient_patterns = [
            {"label": "INGREDIENT", "pattern": [{"LOWER": "salt"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "pepper"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "butter"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "flour"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "sugar"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "oil"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "water"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "milk"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "egg"}, {"LOWER": "eggs", "OP": "?"}]},
            {"label": "INGREDIENT", "pattern": [{"LOWER": "onion"}, {"LOWER": "onions", "OP": "?"}]},
        ]

        # Add all patterns to entity ruler
        all_patterns = unit_patterns + quantity_patterns + ingredient_patterns
        self.entity_ruler.add_patterns(all_patterns)

        # Set up category mappings
        self._setup_category_mappings()

    def _setup_category_mappings(self) -> None:
        """Set up ingredient category mappings."""
        self.category_keywords = {
            IngredientCategory.PROTEIN: {
                "chicken", "beef", "pork", "fish", "salmon", "tuna", "turkey", "lamb",
                "egg", "eggs", "tofu", "beans", "lentils", "chickpeas", "quinoa"
            },
            IngredientCategory.VEGETABLE: {
                "onion", "onions", "garlic", "carrot", "carrots", "celery", "potato", "potatoes",
                "tomato", "tomatoes", "pepper", "peppers", "spinach", "lettuce", "broccoli",
                "cauliflower", "mushroom", "mushrooms", "zucchini", "cucumber", "corn"
            },
            IngredientCategory.FRUIT: {
                "apple", "apples", "banana", "bananas", "orange", "oranges", "lemon", "lemons",
                "lime", "limes", "berry", "berries", "strawberry", "strawberries", "grape", "grapes"
            },
            IngredientCategory.DAIRY: {
                "milk", "cream", "butter", "cheese", "yogurt", "sour cream", "cottage cheese",
                "mozzarella", "cheddar", "parmesan", "ricotta"
            },
            IngredientCategory.GRAIN: {
                "flour", "bread", "rice", "pasta", "oats", "quinoa", "barley", "wheat",
                "noodles", "crackers", "cereal"
            },
            IngredientCategory.HERB: {
                "basil", "oregano", "thyme", "rosemary", "parsley", "cilantro", "sage",
                "dill", "chives", "mint"
            },
            IngredientCategory.SPICE: {
                "salt", "pepper", "paprika", "cumin", "coriander", "cinnamon", "nutmeg",
                "ginger", "turmeric", "cayenne", "chili", "garlic powder", "onion powder"
            },
            IngredientCategory.FAT: {
                "oil", "olive oil", "vegetable oil", "coconut oil", "butter", "margarine",
                "lard", "shortening"
            }
        }

    async def process_ingredient_text(self, text: str) -> Ingredient:
        """
        Process a single ingredient text string into structured Ingredient.

        Args:
            text: Raw ingredient text (e.g., "2 cups all-purpose flour")

        Returns:
            Structured Ingredient object

        Raises:
            RecipeParsingError: If ingredient cannot be parsed
        """
        if not text or not text.strip():
            raise RecipeParsingError("Empty ingredient text", details={"text": text})

        original_text = text.strip()
        logger.debug(f"Processing ingredient: {original_text}")

        # Clean the text
        cleaned_text = self._clean_ingredient_text(original_text)

        # Parse with spaCy
        doc = self.nlp(cleaned_text)

        # Extract components
        quantity, confidence_quantity = self._extract_quantity(doc, cleaned_text)
        unit, confidence_unit = self._extract_unit(doc, cleaned_text)
        name, confidence_name = self._extract_ingredient_name(doc, cleaned_text)
        category = self._determine_category(name)

        # Calculate overall confidence
        confidence = self._calculate_confidence(
            confidence_quantity, confidence_unit, confidence_name,
            original_text, cleaned_text
        )

        # Validate extracted data
        if not name:
            raise RecipeParsingError(
                f"Could not extract ingredient name from: {original_text}",
                details={"cleaned_text": cleaned_text}
            )

        if quantity <= 0:
            logger.warning(f"Invalid quantity for ingredient: {original_text}")
            quantity = 1.0
            confidence *= 0.5  # Reduce confidence for assumed quantity

        if unit == UnitEnum.TO_TASTE:
            quantity = 1.0  # Normalize "to taste" ingredients

        try:
            return Ingredient(
                name=name,
                quantity=quantity,
                unit=unit,
                category=category,
                confidence=min(confidence, 1.0),  # Ensure confidence <= 1.0
                original_text=original_text
            )
        except Exception as e:
            raise RecipeParsingError(
                f"Failed to create Ingredient object: {str(e)}",
                details={
                    "original_text": original_text,
                    "extracted_name": name,
                    "extracted_quantity": quantity,
                    "extracted_unit": unit.value if unit else None,
                    "error": str(e)
                }
            )

    def _clean_ingredient_text(self, text: str) -> str:
        """
        Clean and normalize ingredient text.

        Args:
            text: Raw ingredient text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())

        # Remove parenthetical notes
        text = re.sub(r'\([^)]*\)', '', text)

        # Remove common recipe annotations
        text = re.sub(r'\b(?:fresh|dried|ground|chopped|diced|minced|sliced|grated)\b', '', text, flags=re.IGNORECASE)

        # Remove extra whitespace again
        text = ' '.join(text.split())

        return text.lower().strip()

    def _extract_quantity(self, doc: Doc, text: str) -> Tuple[float, float]:
        """
        Extract quantity from ingredient text.

        Args:
            doc: spaCy document
            text: Cleaned ingredient text

        Returns:
            Tuple of (quantity, confidence)
        """
        # Look for QUANTITY entities
        quantities = [ent for ent in doc.ents if ent.label_ == "QUANTITY"]

        if quantities:
            quantity_text = quantities[0].text
            quantity, confidence = self._parse_quantity_text(quantity_text)
            if quantity > 0:
                return quantity, confidence

        # Fallback: regex patterns
        quantity, confidence = self._extract_quantity_regex(text)
        if quantity > 0:
            return quantity, confidence

        # Default to 1 if no quantity found
        return 1.0, 0.3

    def _parse_quantity_text(self, text: str) -> Tuple[float, float]:
        """
        Parse quantity from text string.

        Args:
            text: Quantity text

        Returns:
            Tuple of (quantity, confidence)
        """
        text = text.strip().lower()

        # Handle word numbers
        word_numbers = {
            "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }

        if text in word_numbers:
            return float(word_numbers[text]), 0.9

        # Handle fractions
        if '/' in text:
            try:
                fraction = Fraction(text)
                return float(fraction), 0.95
            except (ValueError, ZeroDivisionError):
                pass

        # Handle decimals
        try:
            return float(text), 0.95
        except ValueError:
            pass

        return 0.0, 0.0

    def _extract_quantity_regex(self, text: str) -> Tuple[float, float]:
        """
        Extract quantity using regex patterns.

        Args:
            text: Text to search

        Returns:
            Tuple of (quantity, confidence)
        """
        # Pattern for numbers at start of string
        pattern = r'^(\d+(?:\.\d+)?|\d+\s*\/\s*\d+|\d+\s+\d+\s*\/\s*\d+)'
        match = re.search(pattern, text)

        if match:
            quantity_text = match.group(1)

            # Handle mixed numbers like "1 1/2"
            mixed_match = re.match(r'(\d+)\s+(\d+\s*\/\s*\d+)', quantity_text)
            if mixed_match:
                whole = int(mixed_match.group(1))
                frac = Fraction(mixed_match.group(2).replace(' ', ''))
                return float(whole + frac), 0.9

            # Handle simple fractions
            if '/' in quantity_text:
                try:
                    return float(Fraction(quantity_text.replace(' ', ''))), 0.9
                except (ValueError, ZeroDivisionError):
                    pass

            # Handle decimals
            try:
                return float(quantity_text), 0.9
            except ValueError:
                pass

        return 0.0, 0.0

    def _extract_unit(self, doc: Doc, text: str) -> Tuple[UnitEnum, float]:
        """
        Extract unit from ingredient text.

        Args:
            doc: spaCy document
            text: Cleaned ingredient text

        Returns:
            Tuple of (unit, confidence)
        """
        # Look for UNIT entities
        units = [ent for ent in doc.ents if ent.label_ == "UNIT"]

        if units:
            unit_text = units[0].text
            unit = self._normalize_unit(unit_text)
            if unit:
                return unit, 0.9

        # Fallback: search for unit words in text
        unit = self._find_unit_in_text(text)
        if unit:
            return unit, 0.7

        # Check for special cases
        if any(word in text for word in ["to taste", "taste"]):
            return UnitEnum.TO_TASTE, 0.8

        # Default to "whole" for count items
        return UnitEnum.WHOLE, 0.3

    def _normalize_unit(self, unit_text: str) -> Optional[UnitEnum]:
        """
        Normalize unit text to UnitEnum.

        Args:
            unit_text: Unit text to normalize

        Returns:
            Corresponding UnitEnum or None
        """
        unit_text = unit_text.lower().strip()

        # Direct mapping
        unit_mapping = {
            # Volume
            "cup": UnitEnum.CUP, "cups": UnitEnum.CUP, "c": UnitEnum.CUP,
            "tablespoon": UnitEnum.TABLESPOON, "tablespoons": UnitEnum.TABLESPOON,
            "tbsp": UnitEnum.TABLESPOON, "tbs": UnitEnum.TABLESPOON, "T": UnitEnum.TABLESPOON,
            "teaspoon": UnitEnum.TEASPOON, "teaspoons": UnitEnum.TEASPOON,
            "tsp": UnitEnum.TEASPOON, "t": UnitEnum.TEASPOON,
            "fluid_ounce": UnitEnum.FLUID_OUNCE, "fl oz": UnitEnum.FLUID_OUNCE,
            "pint": UnitEnum.PINT, "pints": UnitEnum.PINT, "pt": UnitEnum.PINT,
            "quart": UnitEnum.QUART, "quarts": UnitEnum.QUART, "qt": UnitEnum.QUART,
            "gallon": UnitEnum.GALLON, "gallons": UnitEnum.GALLON, "gal": UnitEnum.GALLON,
            "liter": UnitEnum.LITER, "liters": UnitEnum.LITER, "l": UnitEnum.LITER, "L": UnitEnum.LITER,
            "milliliter": UnitEnum.MILLILITER, "milliliters": UnitEnum.MILLILITER,
            "ml": UnitEnum.MILLILITER, "mL": UnitEnum.MILLILITER,

            # Weight
            "pound": UnitEnum.POUND, "pounds": UnitEnum.POUND, "lb": UnitEnum.POUND, "lbs": UnitEnum.POUND,
            "ounce": UnitEnum.OUNCE, "ounces": UnitEnum.OUNCE, "oz": UnitEnum.OUNCE, "ozs": UnitEnum.OUNCE,
            "gram": UnitEnum.GRAM, "grams": UnitEnum.GRAM, "g": UnitEnum.GRAM,
            "kilogram": UnitEnum.KILOGRAM, "kilograms": UnitEnum.KILOGRAM, "kg": UnitEnum.KILOGRAM, "kgs": UnitEnum.KILOGRAM,

            # Count
            "whole": UnitEnum.WHOLE,
            "piece": UnitEnum.PIECE, "pieces": UnitEnum.PIECE, "pc": UnitEnum.PIECE, "pcs": UnitEnum.PIECE,
            "clove": UnitEnum.CLOVE, "cloves": UnitEnum.CLOVE,
            "bunch": UnitEnum.BUNCH, "bunches": UnitEnum.BUNCH,
            "package": UnitEnum.PACKAGE, "packages": UnitEnum.PACKAGE,
            "pkg": UnitEnum.PACKAGE, "pkgs": UnitEnum.PACKAGE, "pack": UnitEnum.PACKAGE, "packs": UnitEnum.PACKAGE,

            # Special
            "to_taste": UnitEnum.TO_TASTE, "to taste": UnitEnum.TO_TASTE, "taste": UnitEnum.TO_TASTE,
            "pinch": UnitEnum.PINCH, "pinches": UnitEnum.PINCH,
            "dash": UnitEnum.DASH, "dashes": UnitEnum.DASH,
        }

        return unit_mapping.get(unit_text)

    def _find_unit_in_text(self, text: str) -> Optional[UnitEnum]:
        """
        Find unit by searching for unit keywords in text.

        Args:
            text: Text to search

        Returns:
            Found unit or None
        """
        words = text.lower().split()

        for word in words:
            unit = self._normalize_unit(word)
            if unit:
                return unit

        return None

    def _extract_ingredient_name(self, doc: Doc, text: str) -> Tuple[str, float]:
        """
        Extract ingredient name from text.

        Args:
            doc: spaCy document
            text: Cleaned ingredient text

        Returns:
            Tuple of (ingredient_name, confidence)
        """
        # Remove quantity and unit from text
        text_parts = text.split()
        cleaned_parts = []
        skip_next = False

        for i, part in enumerate(text_parts):
            if skip_next:
                skip_next = False
                continue

            # Skip if looks like quantity
            if self._looks_like_quantity(part):
                continue

            # Skip if looks like unit
            if self._normalize_unit(part):
                continue

            # Skip unit abbreviations that might be missed
            if part in ["of", "and", "&"]:
                continue

            cleaned_parts.append(part)

        # Join remaining parts
        name = ' '.join(cleaned_parts).strip()

        # Remove common qualifiers
        qualifiers = ["fresh", "dried", "ground", "chopped", "diced", "minced", "sliced", "grated", "large", "small", "medium"]
        for qualifier in qualifiers:
            name = re.sub(rf'\b{qualifier}\b', '', name, flags=re.IGNORECASE)

        name = ' '.join(name.split()).strip()

        if not name:
            # Fallback: use original text without first few words
            fallback_parts = text.split()[2:]  # Skip first 2 words (likely quantity/unit)
            name = ' '.join(fallback_parts).strip()

        confidence = 0.8 if name else 0.3
        return name, confidence

    def _looks_like_quantity(self, text: str) -> bool:
        """Check if text looks like a quantity."""
        # Numbers
        if re.match(r'^\d+(?:\.\d+)?$', text):
            return True

        # Fractions
        if re.match(r'^\d+\/\d+$', text):
            return True

        # Word numbers
        word_numbers = {"a", "an", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
        return text.lower() in word_numbers

    def _determine_category(self, ingredient_name: str) -> Optional[IngredientCategory]:
        """
        Determine ingredient category based on name.

        Args:
            ingredient_name: Name of the ingredient

        Returns:
            Detected category or None
        """
        if not ingredient_name:
            return None

        name_lower = ingredient_name.lower()

        for category, keywords in self.category_keywords.items():
            if any(keyword in name_lower for keyword in keywords):
                return category

        return IngredientCategory.OTHER

    def _calculate_confidence(self, conf_quantity: float, conf_unit: float, conf_name: float,
                             original_text: str, cleaned_text: str) -> float:
        """
        Calculate overall confidence score.

        Args:
            conf_quantity: Confidence in quantity extraction
            conf_unit: Confidence in unit extraction
            conf_name: Confidence in name extraction
            original_text: Original ingredient text
            cleaned_text: Cleaned ingredient text

        Returns:
            Overall confidence score (0.0 to 1.0)
        """
        # Base confidence is average of component confidences
        base_confidence = (conf_quantity + conf_unit + conf_name) / 3

        # Boost confidence for well-structured text
        if len(original_text.split()) >= 3:  # Has quantity, unit, and name
            base_confidence += 0.1

        # Reduce confidence for very short or very long text
        if len(original_text.split()) < 2:
            base_confidence -= 0.2
        elif len(original_text.split()) > 8:
            base_confidence -= 0.1

        # Reduce confidence if heavily cleaned
        if len(cleaned_text) < len(original_text) * 0.6:
            base_confidence -= 0.1

        return max(0.0, min(1.0, base_confidence))

    async def process_ingredients_batch(self, ingredient_texts: List[str]) -> List[Ingredient]:
        """
        Process multiple ingredient texts in batch.

        Args:
            ingredient_texts: List of ingredient text strings

        Returns:
            List of processed Ingredient objects
        """
        ingredients = []
        for text in ingredient_texts:
            try:
                ingredient = await self.process_ingredient_text(text)
                ingredients.append(ingredient)
            except RecipeParsingError as e:
                logger.warning(f"Failed to process ingredient '{text}': {e.message}")
                # Continue processing other ingredients
                continue

        return ingredients


# Convenience function for external usage
async def process_ingredient_text(text: str) -> Ingredient:
    """
    Process a single ingredient text string into structured Ingredient.

    Convenience function that creates an IngredientNLPProcessor instance
    and processes the ingredient text.

    Args:
        text: Raw ingredient text

    Returns:
        Structured Ingredient object

    Raises:
        RecipeParsingError: If ingredient cannot be parsed
    """
    processor = IngredientNLPProcessor()
    return await processor.process_ingredient_text(text)


async def process_ingredients_batch(ingredient_texts: List[str]) -> List[Ingredient]:
    """
    Process multiple ingredient texts in batch.

    Convenience function for processing multiple ingredients efficiently.

    Args:
        ingredient_texts: List of ingredient text strings

    Returns:
        List of processed Ingredient objects
    """
    processor = IngredientNLPProcessor()
    return await processor.process_ingredients_batch(ingredient_texts)