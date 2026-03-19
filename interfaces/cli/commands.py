"""
CLI commands for Holiday Meal Planner.

Implements Typer-based command-line interface with commands for processing
recipes, generating grocery lists, and managing meal planning workflows.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Annotated
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

from core.models import MenuItemInput
from core.meal_planner import (
    MealPlannerOrchestrator, MealPlanningRequest,
    plan_holiday_meal, generate_grocery_list, process_recipe_url
)
from interfaces.cli.formatters import CLIFormatter, print_grocery_list, print_timeline, format_error_simple
from shared.exceptions import MealPlannerException
from shared.config import get_settings
from shared.i18n import set_language, Language


# Initialize CLI components
console = Console()
formatter = CLIFormatter(console)

# Create Typer app
app = typer.Typer(
    name="holiday-planner",
    help="AI-powered holiday meal planner with recipe processing and timeline generation",
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]}
)


@app.callback()
def main_callback(
    language: Annotated[Optional[str], typer.Option(
        "--language", "-l",
        help="Language for output (en/he)",
        metavar="LANG"
    )] = "en"
):
    """
    Holiday Meal Planner - AI-powered meal planning with recipe processing.

    Supports Hebrew (he) and English (en) output.
    """
    # Set the language for localization
    try:
        lang = Language.HEBREW if language.lower() in ["he", "hebrew", "עברית"] else Language.ENGLISH
        set_language(lang)
    except ValueError:
        console.print(f"[yellow]⚠️  Unknown language '{language}', defaulting to English[/yellow]")
        set_language(Language.ENGLISH)


@app.command("process")
def process_recipes(
    urls: Annotated[Optional[List[str]], typer.Option("--url", "-u", help="Recipe URLs to process")] = None,
    descriptions: Annotated[Optional[List[str]], typer.Option("--description", "-d", help="Recipe descriptions")] = None,
    serving_size: Annotated[int, typer.Option("--serving-size", "-s", help="Number of people to serve")] = 8,
    confidence: Annotated[float, typer.Option("--confidence", "-c", help="Minimum confidence threshold (0.0-1.0)")] = 0.6,
    similarity: Annotated[float, typer.Option("--similarity", help="Similarity threshold for consolidation (0-100)")] = 85.0,
    table_format: Annotated[bool, typer.Option("--table/--list", help="Output format")] = True,
    details: Annotated[bool, typer.Option("--details", help="Show detailed information")] = False,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Save output to file")] = None,
    # Timeline options
    timeline: Annotated[bool, typer.Option("--timeline", "-t", help="Generate preparation timeline")] = False,
    meal_date: Annotated[Optional[str], typer.Option("--meal-date", "-m", help="Meal date (YYYY-MM-DD HH:MM)")] = None,
    max_prep_days: Annotated[int, typer.Option("--max-prep-days", help="Maximum days of preparation")] = 7,
    max_daily_hours: Annotated[int, typer.Option("--max-daily-hours", help="Maximum hours per day")] = 4,
    language: Annotated[str, typer.Option("--language", "-l", help="Language for output (en/he)")] = "en"
):
    """
    Process recipes and generate consolidated grocery list.

    Process multiple recipes from URLs or descriptions to create a unified
    grocery list with intelligent ingredient consolidation.

    Examples:
        # Process single URL
        holiday-planner process -u "https://example.com/recipe"

        # Process multiple URLs
        holiday-planner process -u url1 -u url2 --serving-size 12

        # Process descriptions
        holiday-planner process -d "turkey" -d "mashed potatoes" -d "stuffing"

        # Mix URLs and descriptions
        holiday-planner process -u "https://example.com/recipe" -d "green bean casserole"
    """
    try:
        # Set language for output
        lang = Language.HEBREW if language.lower() in ["he", "hebrew", "עברית"] else Language.ENGLISH
        set_language(lang)

        # Validate inputs
        if not urls and not descriptions:
            rprint("[red]❌ Error: Must provide at least one URL or description[/red]")
            rprint("Use [cyan]--url[/cyan] or [cyan]--description[/cyan] to specify recipes")
            raise typer.Exit(1)

        if confidence < 0.0 or confidence > 1.0:
            rprint("[red]❌ Error: Confidence must be between 0.0 and 1.0[/red]")
            raise typer.Exit(1)

        if similarity < 0 or similarity > 100:
            rprint("[red]❌ Error: Similarity threshold must be between 0 and 100[/red]")
            raise typer.Exit(1)

        # Create menu items
        menu_items = []

        if urls:
            for url in urls:
                menu_item = MenuItemInput(source_url=url, serving_size=serving_size)
                menu_items.append(menu_item)

        if descriptions:
            for description in descriptions:
                menu_item = MenuItemInput(description=description, serving_size=serving_size)
                menu_items.append(menu_item)

        # Parse meal date if provided
        meal_datetime = None
        if meal_date:
            try:
                if ' ' in meal_date:
                    meal_datetime = datetime.strptime(meal_date, "%Y-%m-%d %H:%M")
                else:
                    meal_datetime = datetime.strptime(meal_date, "%Y-%m-%d")
                    meal_datetime = meal_datetime.replace(hour=18, minute=0)  # Default to 6 PM
            except ValueError:
                rprint("[red]❌ Error: Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[/red]")
                raise typer.Exit(1)
        elif timeline:
            # Default to next Sunday at 6 PM if timeline requested but no date provided
            today = datetime.now()
            days_ahead = 6 - today.weekday()  # Sunday = 6
            if days_ahead <= 0:
                days_ahead += 7
            meal_datetime = today + timedelta(days=days_ahead)
            meal_datetime = meal_datetime.replace(hour=18, minute=0, second=0, microsecond=0)

        console.print(f"\n🔄 Processing {len(menu_items)} recipes for {serving_size} people...")
        if timeline and meal_datetime:
            meal_str = meal_datetime.strftime("%A, %B %d at %I:%M %p")
            console.print(f"📅 Generating timeline for meal on {meal_str}")

        # Create meal planning request
        request = MealPlanningRequest(
            menu_items=menu_items,
            serving_size=serving_size,
            confidence_threshold=confidence,
            similarity_threshold=similarity,
            include_timeline=timeline
        )

        # Initialize orchestrator and process
        orchestrator = MealPlannerOrchestrator()

        if timeline and meal_datetime:
            # Generate complete meal plan with timeline
            from core.agents.timeline_generator import TimelineGeneratorAgent, TimelineGenerationRequest

            timeline_agent = TimelineGeneratorAgent()
            timeline_request = TimelineGenerationRequest(
                menu_items=menu_items,
                meal_datetime=meal_datetime,
                max_prep_days=max_prep_days,
                max_daily_hours=max_daily_hours,
                confidence_threshold=confidence
            )

            # Process both grocery list and timeline
            planning_response = asyncio.run(orchestrator.plan_meal(request))
            timeline_response = asyncio.run(timeline_agent.generate_timeline(timeline_request))

            # Display results
            grocery_list = planning_response.processing_result.grocery_list
            prep_timeline = timeline_response.timeline

            # Show grocery list
            if table_format:
                table = formatter.format_grocery_list_table(grocery_list)
                console.print(table)
            else:
                formatted_list = formatter.format_grocery_list(grocery_list, show_details=details)
                console.print(formatted_list)

            # Show timeline
            if table_format:
                timeline_table = formatter.format_timeline_table(prep_timeline)
                console.print(timeline_table)
            else:
                formatted_timeline = formatter.format_timeline(prep_timeline, compact=not details)
                console.print(formatted_timeline)

            # Show timeline summary if details requested
            if details:
                timeline_summary = formatter.format_timeline_summary(prep_timeline)
                console.print(Panel(timeline_summary, title="📋 Timeline Summary"))

        else:
            # Generate grocery list only
            grocery_list = asyncio.run(
                generate_grocery_list(menu_items, serving_size)
            )

            # Display results
            if table_format:
                table = formatter.format_grocery_list_table(grocery_list)
                console.print(table)
            else:
                formatted_list = formatter.format_grocery_list(grocery_list, show_details=details)
                console.print(formatted_list)

        # Save to file if requested
        if output:
            if timeline and 'prep_timeline' in locals():
                save_output_with_timeline(grocery_list, prep_timeline, output, table_format)
            else:
                save_output(grocery_list, output, table_format)
            console.print(f"\n💾 Results saved to: [cyan]{output}[/cyan]")

        console.print("\n✅ [green]Processing completed successfully![/green]")

    except MealPlannerException as e:
        error_msg = formatter.format_error_message(e)
        console.print(error_msg)
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {str(e)}[/red]")
        if details:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command("quick")
def quick_recipe(
    recipe: Annotated[str, typer.Argument(help="Recipe URL or description")],
    serving_size: Annotated[int, typer.Option("--serving-size", "-s", help="Number of people to serve")] = 8,
    table_format: Annotated[bool, typer.Option("--table/--list", help="Output format")] = True
):
    """
    Quickly process a single recipe for immediate grocery list.

    Process one recipe URL or description and immediately display
    the grocery list without additional options.

    Examples:
        # Process URL
        holiday-planner quick "https://example.com/turkey-recipe"

        # Process description
        holiday-planner quick "roasted turkey with herbs"
    """
    try:
        console.print(f"\n🔄 Processing recipe for {serving_size} people...")

        # Determine if input is URL or description
        if recipe.startswith(('http://', 'https://')):
            grocery_list = asyncio.run(process_recipe_url(recipe, serving_size))
        else:
            menu_item = MenuItemInput(description=recipe, serving_size=serving_size)
            grocery_list = asyncio.run(generate_grocery_list([menu_item], serving_size))

        # Display results
        print_grocery_list(grocery_list, table_format=table_format)

        console.print("\n✅ [green]Recipe processed successfully![/green]")

    except MealPlannerException as e:
        error_msg = formatter.format_error_message(e)
        console.print(error_msg)
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"\n[red]❌ Error processing recipe: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("interactive")
def interactive_planner():
    """
    Interactive meal planner with guided input.

    Step-by-step guided interface for creating meal plans
    with interactive prompts for recipes and preferences.
    """
    try:
        console.print("\n🍽️  [bold blue]Holiday Meal Planner - Interactive Mode[/bold blue]\n")

        # Get serving size
        serving_size = typer.prompt(
            "How many people are you serving?",
            type=int,
            default=8
        )

        # Collect recipes
        menu_items = []
        console.print("\nLet's add some recipes to your meal plan!")

        while True:
            console.print(f"\n[dim]Currently have {len(menu_items)} recipes[/dim]")

            add_more = Confirm.ask("Add a recipe?" if not menu_items else "Add another recipe?")
            if not add_more:
                break

            # Get recipe input
            input_type = Prompt.ask(
                "Recipe source",
                choices=["url", "description"],
                default="url"
            )

            if input_type == "url":
                url = Prompt.ask("Enter recipe URL")
                menu_item = MenuItemInput(source_url=url, serving_size=serving_size)
            else:
                description = Prompt.ask("Enter recipe description")
                menu_item = MenuItemInput(description=description, serving_size=serving_size)

            menu_items.append(menu_item)
            console.print(f"✅ Added: [green]{url if input_type == 'url' else description}[/green]")

        if not menu_items:
            console.print("[yellow]⚠️  No recipes added. Exiting...[/yellow]")
            return

        # Get processing preferences
        console.print("\n🔧 [bold]Processing Preferences[/bold]")

        confidence = typer.prompt(
            "Minimum confidence threshold (0.0-1.0)",
            type=float,
            default=0.6
        )

        similarity = typer.prompt(
            "Similarity threshold for consolidation (0-100)",
            type=float,
            default=85.0
        )

        table_format = Confirm.ask("Use table format for output?", default=True)
        details = Confirm.ask("Show detailed information?", default=False)

        # Process meal plan
        console.print(f"\n🔄 Processing {len(menu_items)} recipes...")

        grocery_list = asyncio.run(
            generate_grocery_list(menu_items, serving_size)
        )

        # Display results
        console.print("\n" + "="*60)
        console.print("🛒 [bold blue]Your Holiday Grocery List[/bold blue]")
        console.print("="*60)

        if table_format:
            table = formatter.format_grocery_list_table(grocery_list)
            console.print(table)
        else:
            formatted_list = formatter.format_grocery_list(grocery_list, show_details=details)
            console.print(formatted_list)

        # Ask about saving
        save_file = Confirm.ask("\nSave grocery list to file?")
        if save_file:
            filename = Prompt.ask("Filename", default="grocery_list.txt")
            output_path = Path(filename)
            save_output(grocery_list, output_path, table_format)
            console.print(f"💾 Saved to: [cyan]{output_path}[/cyan]")

        console.print("\n✅ [green]Meal planning completed successfully![/green]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Interrupted by user[/yellow]")
        raise typer.Exit(0)

    except Exception as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("validate")
def validate_recipe(
    recipe: Annotated[str, typer.Argument(help="Recipe URL or description to validate")],
    check_extraction: Annotated[bool, typer.Option("--check-extraction", help="Test ingredient extraction")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show detailed validation info")] = False
):
    """
    Validate a recipe for processing without full meal planning.

    Check if a recipe URL or description can be successfully processed
    and show what ingredients would be extracted.

    Examples:
        # Validate URL
        holiday-planner validate "https://example.com/recipe"

        # Validate description
        holiday-planner validate "turkey stuffing recipe" --verbose
    """
    try:
        console.print(f"\n🔍 Validating recipe: [cyan]{recipe[:60]}{'...' if len(recipe) > 60 else ''}[/cyan]")

        # Determine input type
        is_url = recipe.startswith(('http://', 'https://'))

        if is_url:
            console.print("📝 Recipe type: [blue]URL[/blue]")

            # Validate URL format and security
            try:
                from shared.validators import validate_url_security
                validate_url_security(recipe)
                console.print("✅ URL security validation: [green]PASSED[/green]")
            except Exception as e:
                console.print(f"❌ URL security validation: [red]FAILED[/red] - {str(e)}")
                return

        else:
            console.print("📝 Recipe type: [blue]Description[/blue]")

        # Test extraction if requested
        if check_extraction:
            console.print("\n🔄 Testing ingredient extraction...")

            if is_url:
                # Test web extraction
                from core.services.web_extractor import extract_recipe_from_url
                try:
                    recipe_data = asyncio.run(extract_recipe_from_url(recipe))
                    console.print("✅ Web extraction: [green]SUCCESS[/green]")

                    if verbose:
                        console.print(f"   Title: {recipe_data.get('title', 'Unknown')}")
                        console.print(f"   Ingredients found: {len(recipe_data.get('ingredients', []))}")
                        console.print(f"   Confidence: {recipe_data.get('confidence', 'Unknown')}")

                        if recipe_data.get('ingredients'):
                            console.print("   Sample ingredients:")
                            for ing in recipe_data['ingredients'][:3]:
                                console.print(f"     • {ing}")

                except Exception as e:
                    console.print(f"❌ Web extraction: [red]FAILED[/red] - {str(e)}")
                    return

            # Test NLP processing
            try:
                from core.services.nlp_processor import process_ingredient_text

                if is_url:
                    # Use extracted ingredients
                    test_ingredients = recipe_data.get('ingredients', [])
                else:
                    # Use description directly
                    test_ingredients = [recipe]

                if test_ingredients:
                    sample_ingredient = test_ingredients[0]
                    processed = asyncio.run(process_ingredient_text(sample_ingredient))

                    console.print("✅ NLP processing: [green]SUCCESS[/green]")

                    if verbose:
                        console.print(f"   Processed: {processed.name}")
                        console.print(f"   Quantity: {processed.quantity}")
                        console.print(f"   Unit: {processed.unit.value}")
                        console.print(f"   Category: {processed.category.value if processed.category else 'Unknown'}")
                        console.print(f"   Confidence: {processed.confidence:.0%}")

            except Exception as e:
                console.print(f"❌ NLP processing: [red]FAILED[/red] - {str(e)}")
                return

        console.print("\n✅ [green]Recipe validation completed successfully![/green]")

        # Suggestions
        console.print("\n💡 [bold]Suggestions:[/bold]")
        if is_url:
            console.print("   • This URL appears to be processable")
            console.print("   • Use [cyan]holiday-planner quick[/cyan] for immediate processing")
        else:
            console.print("   • This description can be used as ingredient input")
            console.print("   • Consider providing more specific details for better results")

        console.print("   • Add to meal plan with [cyan]holiday-planner process[/cyan]")

    except Exception as e:
        console.print(f"\n[red]❌ Validation error: {str(e)}[/red]")
        if verbose:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command("timeline")
def generate_meal_timeline(
    urls: Annotated[Optional[List[str]], typer.Option("--url", "-u", help="Recipe URLs to process")] = None,
    descriptions: Annotated[Optional[List[str]], typer.Option("--description", "-d", help="Recipe descriptions")] = None,
    meal_date: Annotated[str, typer.Option("--meal-date", "-m", help="Meal date and time (YYYY-MM-DD HH:MM)")] = None,
    serving_size: Annotated[int, typer.Option("--serving-size", "-s", help="Number of people to serve")] = 8,
    max_prep_days: Annotated[int, typer.Option("--max-prep-days", help="Maximum days of preparation")] = 7,
    max_daily_hours: Annotated[int, typer.Option("--max-daily-hours", help="Maximum hours per day")] = 4,
    confidence: Annotated[float, typer.Option("--confidence", "-c", help="Minimum confidence threshold (0.0-1.0)")] = 0.6,
    table_format: Annotated[bool, typer.Option("--table/--list", help="Output format")] = True,
    details: Annotated[bool, typer.Option("--details", help="Show detailed information")] = False,
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Save output to file")] = None
):
    """
    Generate optimized preparation timeline for holiday meal.

    Create a day-by-day preparation schedule that optimizes workload distribution
    and ensures all dishes are ready on time for your meal.

    Examples:
        # Timeline for next Sunday dinner
        holiday-planner timeline -u "recipe1.com" -d "turkey" --meal-date "2024-12-25 18:00"

        # Timeline with custom prep constraints
        holiday-planner timeline -u "recipe.com" --max-prep-days 5 --max-daily-hours 3
    """
    try:
        # Validate inputs
        if not urls and not descriptions:
            rprint("[red]❌ Error: Must provide at least one URL or description[/red]")
            rprint("Use [cyan]--url[/cyan] or [cyan]--description[/cyan] to specify recipes")
            raise typer.Exit(1)

        # Parse meal date
        if meal_date:
            try:
                if ' ' in meal_date:
                    meal_datetime = datetime.strptime(meal_date, "%Y-%m-%d %H:%M")
                else:
                    meal_datetime = datetime.strptime(meal_date, "%Y-%m-%d")
                    meal_datetime = meal_datetime.replace(hour=18, minute=0)  # Default to 6 PM
            except ValueError:
                rprint("[red]❌ Error: Invalid date format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM[/red]")
                raise typer.Exit(1)
        else:
            # Default to next Sunday at 6 PM
            today = datetime.now()
            days_ahead = 6 - today.weekday()  # Sunday = 6
            if days_ahead <= 0:
                days_ahead += 7
            meal_datetime = today + timedelta(days=days_ahead)
            meal_datetime = meal_datetime.replace(hour=18, minute=0, second=0, microsecond=0)

        # Create menu items
        menu_items = []
        if urls:
            for url in urls:
                menu_item = MenuItemInput(source_url=url, serving_size=serving_size)
                menu_items.append(menu_item)
        if descriptions:
            for description in descriptions:
                menu_item = MenuItemInput(description=description, serving_size=serving_size)
                menu_items.append(menu_item)

        meal_str = meal_datetime.strftime("%A, %B %d at %I:%M %p")
        console.print(f"\n📅 Generating timeline for meal on {meal_str}")
        console.print(f"🔄 Processing {len(menu_items)} recipes...")

        # Generate timeline
        from core.agents.timeline_generator import TimelineGeneratorAgent, TimelineGenerationRequest

        timeline_agent = TimelineGeneratorAgent()
        timeline_request = TimelineGenerationRequest(
            menu_items=menu_items,
            meal_datetime=meal_datetime,
            max_prep_days=max_prep_days,
            max_daily_hours=max_daily_hours,
            confidence_threshold=confidence
        )

        timeline_response = asyncio.run(timeline_agent.generate_timeline(timeline_request))
        prep_timeline = timeline_response.timeline

        # Display timeline
        if table_format:
            timeline_table = formatter.format_timeline_table(prep_timeline)
            console.print(timeline_table)
        else:
            formatted_timeline = formatter.format_timeline(prep_timeline, compact=not details)
            console.print(formatted_timeline)

        # Show timeline summary if details requested
        if details:
            timeline_summary = formatter.format_timeline_summary(prep_timeline)
            console.print(Panel(timeline_summary, title="📋 Timeline Summary"))

            # Show scheduling metadata
            metadata_panel = Panel(
                f"Tasks generated: {timeline_response.generation_metadata['tasks_generated']}\n"
                f"Days scheduled: {timeline_response.generation_metadata['days_scheduled']}\n"
                f"Critical path length: {timeline_response.generation_metadata['critical_path_length']}\n"
                f"Average confidence: {sum(timeline_response.generation_metadata['confidence_scores']) / len(timeline_response.generation_metadata['confidence_scores']):.0%}",
                title="🔧 Generation Details"
            )
            console.print(metadata_panel)

        # Save to file if requested
        if output:
            save_timeline_output(prep_timeline, output, table_format)
            console.print(f"\n💾 Timeline saved to: [cyan]{output}[/cyan]")

        console.print("\n✅ [green]Timeline generation completed successfully![/green]")

    except Exception as e:
        error_msg = formatter.format_error_message(e)
        console.print(error_msg)
        if details:
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command("config")
def show_config():
    """
    Display current configuration settings.

    Show the current configuration settings for the meal planner
    including security settings, processing limits, and preferences.
    """
    try:
        settings = get_settings()

        console.print("\n⚙️  [bold blue]Holiday Meal Planner Configuration[/bold blue]\n")

        config_table = formatter.console.table()
        config_table.add_column("Setting", style="cyan", min_width=25)
        config_table.add_column("Value", style="white", min_width=30)
        config_table.add_column("Description", style="dim", min_width=40)

        # Add configuration rows
        config_rows = [
            ("Web Request Timeout", f"{settings.web_request_timeout}s", "Timeout for recipe website requests"),
            ("Max Response Size", f"{settings.max_response_size // (1024*1024)}MB", "Maximum size for downloaded recipes"),
            ("Default Confidence", f"{settings.default_confidence_threshold:.0%}", "Default ingredient confidence threshold"),
            ("Default Similarity", f"{settings.default_similarity_threshold:.0f}%", "Default ingredient similarity threshold"),
            ("HTTPS Only", "✅ Enabled", "Only HTTPS URLs are allowed for security"),
            ("Rate Limiting", "✅ Enabled", "Automatic rate limiting between requests"),
        ]

        for setting, value, description in config_rows:
            config_table.add_row(setting, value, description)

        console.print(config_table)

        # Show cache and data locations
        console.print("\n📂 [bold]Data Locations:[/bold]")
        console.print("   • Configuration: Environment variables or defaults")
        console.print("   • Temporary data: Memory only (no persistent storage)")
        console.print("   • Logs: Standard output/error")

        console.print("\n🔒 [bold]Security Features:[/bold]")
        console.print("   • HTTPS-only URL validation")
        console.print("   • Input sanitization and validation")
        console.print("   • Rate limiting for respectful web scraping")
        console.print("   • No persistent storage of sensitive data")

    except Exception as e:
        console.print(f"\n[red]❌ Error loading configuration: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("version")
def show_version():
    """Show version information."""
    console.print("\n🍽️  [bold blue]Holiday Meal Planner[/bold blue]")
    console.print("    Version: [cyan]1.0.0[/cyan]")
    console.print("    AI Framework: [cyan]PydanticAI[/cyan]")
    console.print("    CLI Framework: [cyan]Typer + Rich[/cyan]")
    console.print("\n    🔗 Learn more: [link=https://github.com/your-org/holiday-meal-planner]https://github.com/your-org/holiday-meal-planner[/link]")


# Helper functions

def save_output(grocery_list, output_path: Path, table_format: bool = True):
    """Save grocery list output to file."""
    try:
        if table_format:
            # For table format, save as plain text version
            formatted_text = formatter.format_grocery_list(grocery_list, show_details=True)
        else:
            formatted_text = formatter.format_grocery_list(grocery_list, show_details=False)

        output_path.write_text(formatted_text, encoding='utf-8')

    except Exception as e:
        console.print(f"[red]❌ Failed to save output: {str(e)}[/red]")
        raise


def save_timeline_output(timeline, output_path: Path, table_format: bool = True):
    """Save timeline output to file."""
    try:
        if table_format:
            # For table format, save formatted timeline
            formatted_text = formatter.format_timeline(timeline, compact=False)
        else:
            formatted_text = formatter.format_timeline_summary(timeline)

        output_path.write_text(formatted_text, encoding='utf-8')

    except Exception as e:
        console.print(f"[red]❌ Failed to save timeline: {str(e)}[/red]")
        raise


def save_output_with_timeline(grocery_list, timeline, output_path: Path, table_format: bool = True):
    """Save both grocery list and timeline output to file."""
    try:
        # Format grocery list
        if table_format:
            grocery_text = formatter.format_grocery_list(grocery_list, show_details=True)
        else:
            grocery_text = formatter.format_grocery_list(grocery_list, show_details=False)

        # Format timeline
        timeline_text = formatter.format_timeline(timeline, compact=False)

        # Combine both outputs
        combined_text = f"{grocery_text}\n\n{'='*80}\n\n{timeline_text}"

        output_path.write_text(combined_text, encoding='utf-8')

    except Exception as e:
        console.print(f"[red]❌ Failed to save output: {str(e)}[/red]")
        raise


# Error handling for async operations
def handle_async_errors(func):
    """Decorator to handle common async errors in CLI commands."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Operation cancelled by user[/yellow]")
            raise typer.Exit(0)
        except Exception as e:
            error_msg = format_error_simple(e)
            console.print(error_msg)
            raise typer.Exit(1)
    return wrapper


# Add callback for global options
@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress non-essential output")] = False,
):
    """
    🍽️ Holiday Meal Planner - AI-powered meal planning and grocery list generation.

    Plan your holiday meals with intelligent recipe processing, ingredient consolidation,
    and preparation timeline generation.

    Use [cyan]--help[/cyan] with any command for detailed usage information.
    """
    if verbose and quiet:
        console.print("[red]❌ Error: Cannot use both --verbose and --quiet[/red]")
        raise typer.Exit(1)

    # Configure logging level based on options
    import logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.INFO)


if __name__ == "__main__":
    app()