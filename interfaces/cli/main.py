"""
CLI entry point for Holiday Meal Planner.

Main entry point for the command-line interface using Typer.
Handles application startup, error handling, and global configuration.
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.traceback import install as install_rich_traceback
from rich import print as rprint

from interfaces.cli.commands import app as cli_app
from shared.config import get_settings
from shared.exceptions import MealPlannerException


# Install rich traceback handler for better error display
install_rich_traceback(show_locals=False)

# Initialize console
console = Console()


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Set up logging configuration.

    Args:
        verbose: Enable debug logging
        quiet: Only show error messages
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # Configure basic logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Suppress noisy third-party loggers unless in debug mode
    if not verbose:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('pydantic_ai').setLevel(logging.WARNING)


def check_dependencies() -> bool:
    """
    Check if required dependencies are available.

    Returns:
        True if all dependencies are available, False otherwise
    """
    missing_deps = []

    try:
        import pydantic_ai
    except ImportError:
        missing_deps.append("pydantic-ai")

    try:
        import typer
    except ImportError:
        missing_deps.append("typer")

    try:
        import recipe_scrapers
    except ImportError:
        missing_deps.append("recipe-scrapers")

    try:
        import spacy
    except ImportError:
        missing_deps.append("spacy")

    try:
        import fuzzywuzzy
    except ImportError:
        missing_deps.append("fuzzywuzzy")

    try:
        import pint
    except ImportError:
        missing_deps.append("pint")

    if missing_deps:
        console.print("[red]❌ Missing required dependencies:[/red]")
        for dep in missing_deps:
            console.print(f"   • {dep}")
        console.print("\n[yellow]Please install missing dependencies with:[/yellow]")
        console.print(f"   pip install {' '.join(missing_deps)}")
        return False

    # Check for spaCy model
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        console.print("[yellow]⚠️  spaCy English model not found[/yellow]")
        console.print("Download with: [cyan]python -m spacy download en_core_web_sm[/cyan]")
        console.print("Continuing with basic NLP functionality...\n")

    return True


def validate_environment() -> bool:
    """
    Validate the runtime environment.

    Returns:
        True if environment is valid, False otherwise
    """
    # Check Python version
    if sys.version_info < (3, 8):
        console.print("[red]❌ Python 3.8 or higher is required[/red]")
        console.print(f"Current version: {sys.version}")
        return False

    # Check asyncio support
    try:
        asyncio.get_event_loop()
    except Exception:
        console.print("[red]❌ AsyncIO support not available[/red]")
        return False

    return True


def main() -> None:
    """
    Main entry point for the CLI application.

    Sets up the environment, validates dependencies, and launches the CLI.
    """
    try:
        # Validate environment
        if not validate_environment():
            sys.exit(1)

        # Check dependencies
        if not check_dependencies():
            sys.exit(1)

        # Load settings to validate configuration
        try:
            settings = get_settings()
        except Exception as e:
            console.print(f"[red]❌ Configuration error: {str(e)}[/red]")
            sys.exit(1)

        # Launch CLI application
        cli_app()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
        sys.exit(0)

    except MealPlannerException as e:
        # Handle application-specific errors
        console.print(f"\n[red]❌ {e.__class__.__name__}: {e.message}[/red]")
        if hasattr(e, 'details') and e.details:
            console.print(f"[dim]Details: {e.details}[/dim]")
        sys.exit(1)

    except typer.Exit as e:
        # Handle typer exits (normal or with error codes)
        sys.exit(e.exit_code)

    except Exception as e:
        # Handle unexpected errors
        console.print(f"\n[red]❌ Unexpected error: {str(e)}[/red]")
        console.print("[dim]This may be a bug. Please report it if the issue persists.[/dim]")
        sys.exit(1)


def dev_main() -> None:
    """
    Development entry point with enhanced debugging.

    Alternative entry point for development that includes additional
    debugging features and error reporting.
    """
    import traceback

    try:
        # Enable verbose logging in dev mode
        setup_logging(verbose=True)

        # Show startup banner
        console.print("\n🍽️  [bold blue]Holiday Meal Planner - Development Mode[/bold blue]")
        console.print("[dim]Enhanced debugging and error reporting enabled[/dim]\n")

        main()

    except Exception as e:
        console.print(f"\n[red]❌ Development error: {str(e)}[/red]")
        console.print("\n[bold red]Full traceback:[/bold red]")
        console.print(traceback.format_exc())
        sys.exit(1)


def quick_test() -> None:
    """
    Quick functionality test for development.

    Tests basic functionality without full CLI interface.
    Useful for development and CI/CD validation.
    """
    console.print("🧪 Running quick functionality test...")

    try:
        # Test imports
        from core.models import MenuItemInput, Ingredient, UnitEnum
        from core.meal_planner import MealPlannerOrchestrator

        console.print("✅ Core imports successful")

        # Test basic model creation
        menu_item = MenuItemInput(description="test recipe")
        console.print("✅ Model creation successful")

        # Test ingredient creation
        ingredient = Ingredient(
            name="test ingredient",
            quantity=1.0,
            unit=UnitEnum.CUP,
            confidence=1.0
        )
        console.print("✅ Ingredient model successful")

        console.print("\n🎉 [green]Quick test completed successfully![/green]")

    except Exception as e:
        console.print(f"\n❌ [red]Quick test failed: {str(e)}[/red]")
        sys.exit(1)


# Additional utility functions for CLI

def print_welcome_banner():
    """Print welcome banner for interactive mode."""
    banner = """
╭─────────────────────────────────────────────────╮
│           🍽️  Holiday Meal Planner              │
│                                                 │
│    AI-powered recipe processing and grocery     │
│    list generation for your holiday meals      │
╰─────────────────────────────────────────────────╯
    """
    console.print(banner, style="bold blue")


def print_help_hint():
    """Print helpful hints for new users."""
    hints = [
        "💡 Start with: [cyan]holiday-planner quick \"recipe-url\"[/cyan]",
        "💡 Interactive mode: [cyan]holiday-planner interactive[/cyan]",
        "💡 Get help: [cyan]holiday-planner --help[/cyan]",
        "💡 Validate recipes: [cyan]holiday-planner validate \"recipe-url\"[/cyan]"
    ]

    console.print("\n[bold]Quick Start Hints:[/bold]")
    for hint in hints:
        console.print(f"   {hint}")
    console.print()


def check_for_updates():
    """Check for application updates (placeholder)."""
    # This would check for updates in a real application
    # For now, it's just a placeholder
    pass


# Entry points for different contexts

def cli_entry():
    """Entry point for normal CLI usage."""
    main()


def dev_entry():
    """Entry point for development usage."""
    dev_main()


def test_entry():
    """Entry point for testing."""
    quick_test()


# Support for direct execution
if __name__ == "__main__":
    # Determine execution mode based on command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "--dev":
        dev_main()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        quick_test()
    else:
        main()