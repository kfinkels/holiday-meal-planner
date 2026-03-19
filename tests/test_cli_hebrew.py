#!/usr/bin/env python3
"""
Test CLI with Hebrew language support
"""

from datetime import datetime
from core.models import ConsolidatedGroceryList, Ingredient, UnitEnum, IngredientCategory
from interfaces.cli.formatters import CLIFormatter
from shared.i18n import set_language, Language
from rich.console import Console

def test_hebrew_cli():
    console = Console()

    # Test Hebrew
    console.print("\n[bold yellow]Testing Hebrew Language Support:[/bold yellow]")
    set_language(Language.HEBREW)

    # Create a simple grocery list
    ingredients = [
        Ingredient(
            name="chicken",
            quantity=2.0,
            unit=UnitEnum.POUND,
            category=IngredientCategory.PROTEIN,
            confidence=0.95
        ),
        Ingredient(
            name="rice",
            quantity=3.0,
            unit=UnitEnum.CUP,
            category=IngredientCategory.GRAIN,
            confidence=0.90
        ),
        Ingredient(
            name="onions",
            quantity=1.0,
            unit=UnitEnum.WHOLE,
            category=IngredientCategory.VEGETABLE,
            confidence=0.85
        )
    ]

    grocery_list = ConsolidatedGroceryList(
        ingredients=ingredients,
        total_items=len(ingredients),
        serving_size=6,
        consolidation_notes=["Test Hebrew consolidation"]
    )

    formatter = CLIFormatter(console)
    formatted_list = formatter.format_grocery_list(grocery_list)
    console.print(formatted_list)

if __name__ == "__main__":
    test_hebrew_cli()