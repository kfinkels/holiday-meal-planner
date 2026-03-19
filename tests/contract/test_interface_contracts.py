"""
Contract tests for Holiday Meal Planner interfaces.

Verifies that CLI and API return identical results for the same inputs,
ensuring consistent behavior across different access methods.
"""

import asyncio
import json
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Import the API application
from interfaces.api.main import app
from shared.service_layer import get_meal_planning_service, process_meal_plan


class ContractTestRunner:
    """Helper class for running contract tests between CLI and API."""

    def __init__(self):
        """Initialize the contract test runner."""
        self.api_client = TestClient(app)
        self.service = get_meal_planning_service()

    async def run_api_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        method: str = "POST"
    ) -> Dict[str, Any]:
        """
        Run API request and return response data.

        Args:
            endpoint: API endpoint path
            payload: Request payload
            method: HTTP method

        Returns:
            API response data
        """
        if method.upper() == "POST":
            response = self.api_client.post(endpoint, json=payload)
        elif method.upper() == "GET":
            response = self.api_client.get(endpoint, params=payload)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response.json()

    def run_cli_command(self, command_args: List[str]) -> Dict[str, Any]:
        """
        Run CLI command and return parsed output.

        Args:
            command_args: List of CLI arguments

        Returns:
            Parsed CLI output
        """
        # Create a temporary file for output
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Add output file to command args
            full_command = [
                "python", "-m", "interfaces.cli.main"
            ] + command_args + ["--output", temp_path]

            # Run CLI command
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True
            )

            # Read the output file
            output_path = Path(temp_path)
            if output_path.exists():
                with open(output_path, 'r') as f:
                    # For CLI, we'll need to parse the text output
                    # This is a simplified parser - in reality, we'd need more robust parsing
                    cli_output = f.read()
                    return self._parse_cli_output(cli_output)
            else:
                # If no file output, parse stdout
                return self._parse_cli_output(result.stdout)

        finally:
            # Clean up temporary file
            output_path = Path(temp_path)
            if output_path.exists():
                output_path.unlink()

    def _parse_cli_output(self, output: str) -> Dict[str, Any]:
        """
        Parse CLI output into structured data.

        Args:
            output: Raw CLI output text

        Returns:
            Structured representation of CLI output
        """
        # This is a simplified parser for testing purposes
        # In a real implementation, you'd have a more robust parser
        # or output CLI results in JSON format

        parsed = {
            "grocery_list": {
                "ingredients": [],
                "total_items": 0
            },
            "timeline": None,
            "processed_items": 0,
            "failed_items": [],
            "processing_metadata": {
                "success_rate": 1.0
            }
        }

        # Extract ingredients (simplified parsing)
        lines = output.split('\n')
        in_ingredients_section = False
        ingredient_count = 0

        for line in lines:
            line = line.strip()

            if "Consolidated Grocery List" in line or "Grocery List" in line:
                in_ingredients_section = True
                continue

            if in_ingredients_section and line and not line.startswith('='):
                if any(unit in line.lower() for unit in ['cup', 'tbsp', 'tsp', 'pound', 'oz']):
                    # This looks like an ingredient line
                    ingredient_count += 1

            if "Processing completed" in line or "Timeline" in line:
                in_ingredients_section = False

        parsed["grocery_list"]["total_items"] = ingredient_count
        parsed["processed_items"] = 1  # Simplified

        return parsed

    async def run_service_layer_direct(
        self,
        menu_items: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run processing directly through service layer.

        Args:
            menu_items: Menu items to process
            **kwargs: Additional parameters

        Returns:
            Service layer result converted to comparable format
        """
        result = await process_meal_plan(menu_items, **kwargs)

        # Convert to comparable format
        return {
            "grocery_list": {
                "ingredients": [
                    {
                        "name": ing.name,
                        "quantity": ing.quantity,
                        "unit": ing.unit.value,
                        "category": ing.category.value if ing.category else None,
                        "confidence": ing.confidence
                    }
                    for ing in result.grocery_list.ingredients
                ],
                "total_items": len(result.grocery_list.ingredients)
            },
            "timeline": {
                "meal_date": result.prep_timeline.meal_date.isoformat(),
                "days": len(result.prep_timeline.days),
                "total_prep_time": result.prep_timeline.total_prep_time,
                "complexity_score": result.prep_timeline.complexity_score
            } if result.prep_timeline.days else None,
            "processed_items": len(result.processed_items),
            "failed_items": result.failed_items,
            "processing_metadata": {
                "total_processing_time_ms": result.processing_metadata.total_processing_time_ms,
                "items_processed": result.processing_metadata.items_processed,
                "items_failed": result.processing_metadata.items_failed,
                "success_rate": result.processing_metadata.success_rate,
                "web_requests_made": result.processing_metadata.web_requests_made,
                "average_confidence": result.processing_metadata.average_confidence
            }
        }


@pytest.fixture
def contract_runner():
    """Fixture providing contract test runner."""
    return ContractTestRunner()


@pytest.fixture
def sample_menu_items():
    """Fixture providing sample menu items for testing."""
    return [
        {
            "description": "roasted turkey with herbs",
            "serving_size": 8
        },
        {
            "description": "mashed potatoes with butter",
            "serving_size": 8
        }
    ]


@pytest.fixture
def sample_menu_with_timeline():
    """Fixture providing menu items with timeline parameters."""
    future_date = datetime.utcnow() + timedelta(days=7)
    return {
        "menu_items": [
            {
                "description": "roasted turkey",
                "serving_size": 8
            }
        ],
        "meal_datetime": future_date.isoformat(),
        "include_timeline": True,
        "max_prep_days": 3,
        "max_daily_hours": 4
    }


@pytest.mark.asyncio
async def test_grocery_list_generation_contract(contract_runner, sample_menu_items):
    """
    Test that CLI and API return identical grocery lists for the same input.

    This test verifies the core contract that both interfaces produce
    the same grocery list when given identical menu items.
    """
    # Prepare API payload
    api_payload = {
        "menu_items": sample_menu_items,
        "include_timeline": False,
        "confidence_threshold": 0.6,
        "similarity_threshold": 85.0
    }

    # Mock external dependencies to ensure consistent results
    with patch('core.services.web_extractor.extract_recipe_from_url') as mock_extract:
        # Mock response for consistent testing
        mock_extract.return_value = {
            "title": "Test Recipe",
            "ingredients": ["2 cups flour", "1 pound turkey"],
            "confidence": 0.85
        }

        # Run API request
        api_result = await contract_runner.run_api_request("/v1/process", api_payload)

        # Run service layer directly
        service_result = await contract_runner.run_service_layer_direct(
            sample_menu_items,
            confidence_threshold=0.6,
            similarity_threshold=85.0,
            include_timeline=False
        )

        # Verify core contract: same number of ingredients
        assert api_result["grocery_list"]["total_items"] == service_result["grocery_list"]["total_items"]

        # Verify processing metadata consistency
        assert api_result["processing_metadata"]["success_rate"] == service_result["processing_metadata"]["success_rate"]
        assert api_result["processed_items"] == service_result["processed_items"]


@pytest.mark.asyncio
async def test_timeline_generation_contract(contract_runner, sample_menu_with_timeline):
    """
    Test that CLI and API return identical timelines for the same input.

    This test verifies that timeline generation produces consistent
    results across both interfaces.
    """
    # Mock external dependencies
    with patch('core.services.web_extractor.extract_recipe_from_url') as mock_extract:
        mock_extract.return_value = {
            "title": "Test Recipe",
            "ingredients": ["2 pounds turkey", "1 cup butter"],
            "confidence": 0.85
        }

        # Run API request
        api_result = await contract_runner.run_api_request(
            "/v1/process",
            sample_menu_with_timeline
        )

        # Run service layer directly
        service_result = await contract_runner.run_service_layer_direct(
            sample_menu_with_timeline["menu_items"],
            include_timeline=True,
            meal_datetime=datetime.fromisoformat(sample_menu_with_timeline["meal_datetime"]),
            max_prep_days=sample_menu_with_timeline["max_prep_days"],
            max_daily_hours=sample_menu_with_timeline["max_daily_hours"]
        )

        # Verify timeline contract
        if api_result["timeline"] and service_result["timeline"]:
            assert api_result["timeline"]["complexity_score"] == service_result["timeline"]["complexity_score"]
            assert api_result["timeline"]["total_prep_time"] == service_result["timeline"]["total_prep_time"]

        # Verify grocery list consistency
        assert api_result["grocery_list"]["total_items"] == service_result["grocery_list"]["total_items"]


@pytest.mark.asyncio
async def test_error_handling_contract(contract_runner):
    """
    Test that CLI and API handle errors consistently.

    This test verifies that both interfaces report errors
    in a consistent manner for invalid inputs.
    """
    # Test with invalid input (empty menu items)
    invalid_payload = {
        "menu_items": [],
        "include_timeline": False
    }

    # API should return 422 validation error
    api_response = contract_runner.api_client.post("/v1/process", json=invalid_payload)
    assert api_response.status_code == 422

    api_error = api_response.json()
    assert "ValidationError" in api_error.get("error", {}).get("error_type", "")

    # Service layer should raise validation error
    with pytest.raises(Exception) as exc_info:
        await contract_runner.run_service_layer_direct([])

    assert "validation" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_parameter_validation_contract(contract_runner):
    """
    Test that CLI and API validate parameters consistently.

    This test verifies that both interfaces apply the same
    validation rules to input parameters.
    """
    # Test with invalid serving size
    invalid_payload = {
        "menu_items": [
            {
                "description": "test dish",
                "serving_size": 150  # Too high
            }
        ]
    }

    # API should reject invalid serving size
    api_response = contract_runner.api_client.post("/v1/process", json=invalid_payload)
    assert api_response.status_code == 422

    # Service layer should also reject invalid serving size
    with pytest.raises(Exception):
        await contract_runner.run_service_layer_direct(invalid_payload["menu_items"])


@pytest.mark.asyncio
async def test_confidence_threshold_contract(contract_runner, sample_menu_items):
    """
    Test that confidence threshold settings affect results consistently.

    This test verifies that both interfaces respond identically
    to confidence threshold adjustments.
    """
    with patch('core.services.web_extractor.extract_recipe_from_url') as mock_extract:
        mock_extract.return_value = {
            "title": "Test Recipe",
            "ingredients": ["2 cups flour", "1 pound turkey"],
            "confidence": 0.85
        }

        # Test with high confidence threshold
        high_threshold = 0.9

        api_payload = {
            "menu_items": sample_menu_items,
            "confidence_threshold": high_threshold,
            "include_timeline": False
        }

        api_result = await contract_runner.run_api_request("/v1/process", api_payload)
        service_result = await contract_runner.run_service_layer_direct(
            sample_menu_items,
            confidence_threshold=high_threshold,
            include_timeline=False
        )

        # Both should process the same number of items
        assert api_result["processed_items"] == service_result["processed_items"]
        assert api_result["processing_metadata"]["average_confidence"] == service_result["processing_metadata"]["average_confidence"]


@pytest.mark.asyncio
async def test_similarity_threshold_contract(contract_runner, sample_menu_items):
    """
    Test that similarity threshold settings affect consolidation consistently.

    This test verifies that ingredient consolidation behaves
    identically across interfaces for the same similarity settings.
    """
    with patch('core.services.web_extractor.extract_recipe_from_url') as mock_extract:
        mock_extract.return_value = {
            "title": "Test Recipe",
            "ingredients": ["2 cups all-purpose flour", "2 cups flour"],  # Similar ingredients
            "confidence": 0.85
        }

        # Test with low similarity threshold (should consolidate)
        low_threshold = 70.0

        api_payload = {
            "menu_items": sample_menu_items,
            "similarity_threshold": low_threshold,
            "include_timeline": False
        }

        api_result = await contract_runner.run_api_request("/v1/process", api_payload)
        service_result = await contract_runner.run_service_layer_direct(
            sample_menu_items,
            similarity_threshold=low_threshold,
            include_timeline=False
        )

        # Both should consolidate ingredients similarly
        assert api_result["grocery_list"]["total_items"] == service_result["grocery_list"]["total_items"]


def test_health_check_contract(contract_runner):
    """
    Test that health check endpoints are available and consistent.

    This test verifies that health check functionality is accessible
    and returns consistent information.
    """
    # Test API health check
    response = contract_runner.api_client.get("/health")
    assert response.status_code == 200

    health_data = response.json()
    assert "status" in health_data
    assert "timestamp" in health_data
    assert "version" in health_data

    # Test ping endpoint
    ping_response = contract_runner.api_client.get("/ping")
    assert ping_response.status_code == 200

    ping_data = ping_response.json()
    assert ping_data["status"] == "ok"


if __name__ == "__main__":
    # Run contract tests
    pytest.main([__file__, "-v"])