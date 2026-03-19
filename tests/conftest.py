"""
Test configuration and fixtures for Holiday Meal Planner.

Provides shared fixtures, test utilities, and mock data for comprehensive testing
across unit, integration, and contract test suites.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, MagicMock
import tempfile
import os

# Import our models and utilities
from core.models import (
    MenuItemInput,
    Ingredient,
    ConsolidatedGroceryList,
    PrepTask,
    DayPlan,
    Timeline,
    ProcessingResult,
    ProcessingMetadata,
    UnitEnum,
    IngredientCategory,
    TimingType,
)
from shared.config import Settings, override_settings
from shared.logging import setup_logging, set_correlation_id


# Test Configuration

@pytest.fixture(scope="session")
def test_settings():
    """Provide test-specific settings."""
    settings = Settings(
        debug=True,
        log_level="DEBUG",
        request_delay=0.1,  # Faster for tests
        request_timeout=5,  # Shorter timeout
        max_menu_items=10,
        confidence_threshold=0.5,
        https_only=False,  # Allow HTTP for testing
        enable_request_logging=False,  # Reduce noise in tests
    )
    override_settings(settings)
    return settings


@pytest.fixture(scope="session")
def setup_test_logging():
    """Setup test logging configuration."""
    setup_logging(log_level="WARNING", json_format=False)


@pytest.fixture(autouse=True)
def test_correlation_id():
    """Set unique correlation ID for each test."""
    correlation_id = set_correlation_id("test")
    yield correlation_id
    # Cleanup is automatic via context vars


# Event Loop Fixtures

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Mock Data Fixtures

@pytest.fixture
def sample_menu_items() -> List[MenuItemInput]:
    """Sample menu items for testing."""
    return [
        MenuItemInput(
            source_url="https://example.com/turkey-recipe",
            serving_size=8,
        ),
        MenuItemInput(
            description="mashed potatoes for 6 people with butter and cream",
            serving_size=6,
        ),
        MenuItemInput(
            source_url="https://example.com/cranberry-sauce",
            serving_size=10,
        ),
        MenuItemInput(
            description="traditional stuffing with sage and celery",
            serving_size=8,
        ),
    ]


@pytest.fixture
def sample_ingredients() -> List[Ingredient]:
    """Sample ingredients for testing."""
    return [
        Ingredient(
            name="turkey",
            quantity=12.0,
            unit=UnitEnum.POUND,
            category=IngredientCategory.PROTEIN,
            confidence=0.95,
            original_text="1 whole turkey (12 lbs)",
        ),
        Ingredient(
            name="potatoes",
            quantity=3.0,
            unit=UnitEnum.POUND,
            category=IngredientCategory.VEGETABLE,
            confidence=0.90,
            original_text="3 pounds russet potatoes",
        ),
        Ingredient(
            name="butter",
            quantity=0.5,
            unit=UnitEnum.CUP,
            category=IngredientCategory.DAIRY,
            confidence=0.85,
            original_text="1/2 cup unsalted butter",
        ),
        Ingredient(
            name="fresh cranberries",
            quantity=2.0,
            unit=UnitEnum.CUP,
            category=IngredientCategory.FRUIT,
            confidence=0.92,
            original_text="2 cups fresh cranberries",
        ),
        Ingredient(
            name="bread cubes",
            quantity=4.0,
            unit=UnitEnum.CUP,
            category=IngredientCategory.GRAIN,
            confidence=0.88,
            original_text="4 cups day-old bread cubes",
        ),
    ]


@pytest.fixture
def sample_grocery_list(sample_ingredients) -> ConsolidatedGroceryList:
    """Sample consolidated grocery list."""
    return ConsolidatedGroceryList(
        ingredients=sample_ingredients,
        total_items=len(sample_ingredients),
        consolidation_notes=[
            "Merged 'unsalted butter' and 'butter' as 'butter'",
            "Converted 1 stick butter to 0.5 cups",
        ],
        serving_size=8,
    )


@pytest.fixture
def sample_prep_tasks() -> List[PrepTask]:
    """Sample preparation tasks."""
    return [
        PrepTask(
            id="task_001",
            dish_name="Turkey",
            task_description="Thaw turkey in refrigerator",
            estimated_duration=60,  # 1 hour active time
            timing_type=TimingType.MAKE_AHEAD,
            optimal_timing="2-3 days before",
            confidence=0.95,
        ),
        PrepTask(
            id="task_002",
            dish_name="Turkey",
            task_description="Prepare turkey brine",
            estimated_duration=30,
            dependencies=["task_001"],
            timing_type=TimingType.DAY_BEFORE,
            optimal_timing="night before",
            confidence=0.90,
        ),
        PrepTask(
            id="task_003",
            dish_name="Stuffing",
            task_description="Cut bread into cubes and let dry",
            estimated_duration=20,
            timing_type=TimingType.MAKE_AHEAD,
            optimal_timing="2 days before",
            confidence=0.85,
        ),
        PrepTask(
            id="task_004",
            dish_name="Cranberry Sauce",
            task_description="Make cranberry sauce",
            estimated_duration=25,
            timing_type=TimingType.DAY_BEFORE,
            optimal_timing="day before",
            confidence=0.92,
        ),
        PrepTask(
            id="task_005",
            dish_name="Turkey",
            task_description="Roast turkey in oven",
            estimated_duration=240,  # 4 hours
            dependencies=["task_002"],
            timing_type=TimingType.DAY_OF_EARLY,
            optimal_timing="morning of meal",
            confidence=0.95,
        ),
    ]


@pytest.fixture
def sample_timeline(sample_prep_tasks) -> Timeline:
    """Sample preparation timeline."""
    meal_date = datetime.utcnow() + timedelta(days=3)

    day_plans = [
        DayPlan(
            day_offset=3,
            date=meal_date - timedelta(days=3),
            tasks=[sample_prep_tasks[0]],  # Thaw turkey
            total_duration=60,
            workload_level=1,
            notes="Start thawing turkey",
        ),
        DayPlan(
            day_offset=2,
            date=meal_date - timedelta(days=2),
            tasks=[sample_prep_tasks[2]],  # Cut bread
            total_duration=20,
            workload_level=1,
            notes="Prep bread for stuffing",
        ),
        DayPlan(
            day_offset=1,
            date=meal_date - timedelta(days=1),
            tasks=[sample_prep_tasks[1], sample_prep_tasks[3]],  # Brine, cranberry sauce
            total_duration=55,
            workload_level=2,
            notes="Final prep day",
        ),
        DayPlan(
            day_offset=0,
            date=meal_date,
            tasks=[sample_prep_tasks[4]],  # Roast turkey
            total_duration=240,
            workload_level=4,
            notes="Meal day - start early!",
        ),
    ]

    return Timeline(
        meal_date=meal_date,
        days=day_plans,
        critical_path=["task_001", "task_002", "task_005"],
        total_prep_time=375,  # Sum of all task durations
        complexity_score=6,
        optimization_notes=[
            "Maximized make-ahead tasks",
            "Balanced workload across days",
            "Critical path optimized for turkey preparation",
        ],
    )


@pytest.fixture
def sample_processing_result(sample_menu_items, sample_grocery_list, sample_timeline) -> ProcessingResult:
    """Sample complete processing result."""
    metadata = ProcessingMetadata(
        total_processing_time_ms=45000,  # 45 seconds
        items_processed=4,
        items_failed=0,
        success_rate=1.0,
        web_requests_made=2,  # Two URLs
        average_confidence=0.90,
    )

    return ProcessingResult(
        grocery_list=sample_grocery_list,
        prep_timeline=sample_timeline,
        processed_items=sample_menu_items,
        failed_items=[],
        processing_metadata=metadata,
    )


# Mock Web Response Fixtures

@pytest.fixture
def mock_recipe_html():
    """Mock HTML content for recipe parsing."""
    return """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org/",
            "@type": "Recipe",
            "name": "Perfect Roast Turkey",
            "recipeIngredient": [
                "1 whole turkey (12-14 lbs)",
                "2 tablespoons olive oil",
                "1 tablespoon salt",
                "1 teaspoon black pepper",
                "2 cups chicken broth"
            ],
            "recipeInstructions": [
                "Preheat oven to 325°F",
                "Rinse turkey and pat dry",
                "Rub with oil and seasonings",
                "Roast 15 minutes per pound"
            ],
            "prepTime": "PT30M",
            "cookTime": "PT3H",
            "recipeYield": "8 servings"
        }
        </script>
    </head>
    <body>
        <h1>Perfect Roast Turkey</h1>
        <div class="ingredients">
            <ul>
                <li>1 whole turkey (12-14 lbs)</li>
                <li>2 tablespoons olive oil</li>
                <li>1 tablespoon salt</li>
                <li>1 teaspoon black pepper</li>
                <li>2 cups chicken broth</li>
            </ul>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_web_responses(mock_recipe_html):
    """Mock responses for different URLs."""
    return {
        "https://example.com/turkey-recipe": {
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "text": mock_recipe_html,
        },
        "https://example.com/cranberry-sauce": {
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "text": """
            <html>
            <body>
                <h1>Cranberry Sauce</h1>
                <ul class="ingredients">
                    <li>2 cups fresh cranberries</li>
                    <li>1 cup sugar</li>
                    <li>1/2 cup water</li>
                    <li>1 orange zest</li>
                </ul>
            </body>
            </html>
            """,
        },
        "https://example.com/not-found": {
            "status_code": 404,
            "headers": {"content-type": "text/html"},
            "text": "<html><body>Not Found</body></html>",
        },
        "https://example.com/timeout": {
            "status_code": None,  # Indicates timeout
            "exception": "ConnectionTimeout",
        },
    }


# Mock Service Fixtures

@pytest.fixture
def mock_web_extractor():
    """Mock web extraction service."""
    mock = Mock()
    mock.extract_recipe_async = MagicMock()

    # Default successful response
    mock.extract_recipe_async.return_value = {
        "title": "Sample Recipe",
        "ingredients": [
            {"name": "turkey", "quantity": 1, "unit": "whole"},
            {"name": "salt", "quantity": 2, "unit": "tablespoon"},
        ],
        "prep_time": 30,
        "cook_time": 180,
        "servings": 8,
    }

    return mock


@pytest.fixture
def mock_nlp_processor():
    """Mock NLP processing service."""
    mock = Mock()
    mock.extract_ingredients = MagicMock()

    # Default successful response
    mock.extract_ingredients.return_value = [
        {
            "name": "potatoes",
            "quantity": 3.0,
            "unit": "pound",
            "confidence": 0.90,
            "original_text": "3 pounds potatoes",
        }
    ]

    return mock


@pytest.fixture
def mock_consolidator():
    """Mock ingredient consolidation service."""
    mock = Mock()
    mock.consolidate_ingredients = MagicMock()

    def consolidate_side_effect(ingredient_lists):
        # Simple consolidation - just flatten and dedupe by name
        all_ingredients = []
        for ingredients in ingredient_lists:
            all_ingredients.extend(ingredients)

        consolidated = {}
        for ing in all_ingredients:
            name = ing["name"]
            if name in consolidated:
                consolidated[name]["quantity"] += ing["quantity"]
            else:
                consolidated[name] = ing.copy()

        return {
            "ingredients": list(consolidated.values()),
            "consolidation_notes": [f"Merged {len(all_ingredients)} ingredients into {len(consolidated)}"],
        }

    mock.consolidate_ingredients.side_effect = consolidate_side_effect
    return mock


@pytest.fixture
def mock_scheduler():
    """Mock scheduling service."""
    mock = Mock()
    mock.generate_timeline = MagicMock()

    # Default timeline response
    mock.generate_timeline.return_value = {
        "timeline": "sample timeline data",
        "critical_path": ["task_1", "task_2"],
        "optimization_notes": ["Balanced workload"],
    }

    return mock


# Temporary File Fixtures

@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_file():
    """Temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
        yield f.name
    os.unlink(f.name)


# Database/Storage Fixtures (for future use)

@pytest.fixture
def mock_storage():
    """Mock storage service for caching tests."""
    storage = {}

    class MockStorage:
        def get(self, key):
            return storage.get(key)

        def set(self, key, value, ttl=None):
            storage[key] = value

        def delete(self, key):
            storage.pop(key, None)

        def clear(self):
            storage.clear()

    return MockStorage()


# Error Simulation Fixtures

@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        "network_error": {
            "exception": "ConnectionError",
            "message": "Network connection failed",
        },
        "timeout_error": {
            "exception": "TimeoutError",
            "message": "Request timed out",
        },
        "parse_error": {
            "exception": "RecipeParsingError",
            "message": "Could not parse recipe content",
        },
        "validation_error": {
            "exception": "ValidationError",
            "message": "Invalid input data",
        },
        "security_error": {
            "exception": "SecurityError",
            "message": "URL blocked by security policy",
        },
    }


# Performance Testing Fixtures

@pytest.fixture
def performance_timer():
    """Timer for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        def elapsed_ms(self):
            if self.start_time and self.end_time:
                return int((self.end_time - self.start_time) * 1000)
            return None

    return Timer()


# Test Utilities

def assert_valid_ingredient(ingredient: Dict[str, Any]):
    """Assert that ingredient data is valid."""
    assert "name" in ingredient
    assert "quantity" in ingredient
    assert "unit" in ingredient
    assert isinstance(ingredient["quantity"], (int, float))
    assert ingredient["quantity"] > 0
    assert len(ingredient["name"].strip()) > 0


def assert_valid_grocery_list(grocery_list: Dict[str, Any]):
    """Assert that grocery list data is valid."""
    assert "ingredients" in grocery_list
    assert "total_items" in grocery_list
    assert isinstance(grocery_list["ingredients"], list)
    assert len(grocery_list["ingredients"]) > 0
    assert grocery_list["total_items"] == len(grocery_list["ingredients"])

    for ingredient in grocery_list["ingredients"]:
        assert_valid_ingredient(ingredient)


def assert_valid_timeline(timeline: Dict[str, Any]):
    """Assert that timeline data is valid."""
    assert "meal_date" in timeline
    assert "days" in timeline
    assert "total_prep_time" in timeline
    assert isinstance(timeline["days"], list)
    assert len(timeline["days"]) > 0

    # Check days are ordered correctly
    day_offsets = [day["day_offset"] for day in timeline["days"]]
    assert day_offsets == sorted(day_offsets, reverse=True)


# Parametrized Test Data

@pytest.fixture(params=[
    {"serving_size": 4, "expected_scale": 0.5},
    {"serving_size": 8, "expected_scale": 1.0},
    {"serving_size": 12, "expected_scale": 1.5},
    {"serving_size": 16, "expected_scale": 2.0},
])
def serving_size_scenarios(request):
    """Different serving size scenarios for scaling tests."""
    return request.param


@pytest.fixture(params=[
    "https://allrecipes.com/recipe/123/turkey",
    "https://foodnetwork.com/recipes/turkey-recipe",
    "https://example.com/simple-recipe",
])
def valid_recipe_urls(request):
    """Valid recipe URLs for testing."""
    return request.param


@pytest.fixture(params=[
    "mashed potatoes for 6 people",
    "traditional thanksgiving stuffing with sage",
    "homemade cranberry sauce with orange zest",
    "green bean casserole with crispy onions",
])
def valid_descriptions(request):
    """Valid dish descriptions for testing."""
    return request.param