"""
CLI output formatters for Holiday Meal Planner.

Provides human-readable formatting for grocery lists, timelines,
error messages, and processing results with rich console output.
"""

import math
from typing import List, Dict, Any, Optional
from datetime import datetime
from textwrap import wrap, dedent

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.progress import track
from rich import box

from core.models import (
    ConsolidatedGroceryList, Ingredient, Timeline, DayPlan, PrepTask,
    ProcessingResult, IngredientCategory, UnitEnum
)
from shared.i18n import get_text, get_category_name, get_unit_name, is_rtl


class CLIFormatter:
    """
    Formatter for CLI output with rich console features.

    Provides human-readable formatting for all meal planner outputs
    including grocery lists, timelines, and error messages.
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI formatter with console."""
        self.console = console or Console()

    def format_grocery_list(self, grocery_list: ConsolidatedGroceryList, show_details: bool = False) -> str:
        """
        Format consolidated grocery list for display.

        Args:
            grocery_list: Consolidated grocery list to format
            show_details: Whether to show detailed information

        Returns:
            Formatted grocery list string
        """
        output = []

        # Header
        header = get_text("grocery_list.header", serving_size=grocery_list.serving_size)
        if grocery_list.total_items:
            header += " " + get_text("grocery_list.items_count", total_items=grocery_list.total_items)

        output.append(self._create_header(header))

        # Group ingredients by category
        categorized_ingredients = self._group_by_category(grocery_list.ingredients)

        # Format each category
        for category, ingredients in categorized_ingredients.items():
            if not ingredients:
                continue

            category_header = self._format_category_name(category)
            output.append(f"\n{category_header}")
            output.append("─" * len(category_header))

            for ingredient in ingredients:
                formatted_ingredient = self._format_ingredient(ingredient, show_details)
                output.append(f"  {formatted_ingredient}")

        # Add consolidation notes if requested
        if show_details and grocery_list.consolidation_notes:
            output.append("\n" + self._format_consolidation_notes(grocery_list.consolidation_notes))

        # Add generation timestamp
        timestamp = grocery_list.generated_at.strftime("%Y-%m-%d %H:%M")
        output.append("\n" + get_text("grocery_list.generated", timestamp=timestamp))

        return "\n".join(output)

    def format_grocery_list_table(self, grocery_list: ConsolidatedGroceryList) -> Table:
        """
        Format grocery list as a rich table.

        Args:
            grocery_list: Consolidated grocery list to format

        Returns:
            Rich table object
        """
        table = Table(
            title=f"🛒 Grocery List ({grocery_list.total_items} items for {grocery_list.serving_size} people)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )

        table.add_column("Category", style="cyan", min_width=12)
        table.add_column("Ingredient", style="white", min_width=20)
        table.add_column("Quantity", justify="right", style="green", min_width=10)
        table.add_column("Unit", style="yellow", min_width=8)

        if any(ing.confidence < 0.8 for ing in grocery_list.ingredients):
            table.add_column("Confidence", justify="center", style="blue", min_width=10)

        # Group by category and add rows
        categorized_ingredients = self._group_by_category(grocery_list.ingredients)

        for category, ingredients in categorized_ingredients.items():
            category_display = self._format_category_name(category)
            first_item = True

            for ingredient in ingredients:
                # Format quantity with appropriate precision
                quantity_str = self._format_quantity(ingredient.quantity)

                row = [
                    category_display if first_item else "",
                    ingredient.name.title(),
                    quantity_str,
                    ingredient.unit.value.replace("_", " ").title()
                ]

                # Add confidence if showing
                if table.columns[-1].header == "Confidence":
                    confidence_str = self._format_confidence(ingredient.confidence)
                    row.append(confidence_str)

                table.add_row(*row)
                first_item = False

        return table

    def format_timeline(self, timeline: Timeline, compact: bool = False) -> str:
        """
        Format preparation timeline for display.

        Args:
            timeline: Timeline to format
            compact: Whether to use compact format

        Returns:
            Formatted timeline string
        """
        if not timeline.days:
            return "📅 No preparation timeline available"

        output = []

        # Header
        meal_date = timeline.meal_date.strftime("%A, %B %d, %Y at %I:%M %p")
        header = get_text("timeline.header", meal_date=meal_date)
        output.append(self._create_header(header))

        # Summary statistics
        total_hours = timeline.total_prep_time // 60
        total_minutes = timeline.total_prep_time % 60
        complexity_stars = "★" * timeline.complexity_score + "☆" * (10 - timeline.complexity_score)

        summary = get_text("timeline.total_prep_time", hours=total_hours, minutes=total_minutes)
        summary += "  •  " + get_text("timeline.complexity", stars=complexity_stars, score=timeline.complexity_score)
        output.append(f"\n{summary}")

        # Format each day
        for day in timeline.days:
            day_output = self._format_day_plan(day, compact)
            output.append(day_output)

        # Add optimization notes
        if timeline.optimization_notes:
            output.append("\n" + get_text("timeline.optimization_notes"))
            for note in timeline.optimization_notes:
                wrapped_note = self._wrap_text(note, prefix="   • ")
                output.append(wrapped_note)

        return "\n".join(output)

    def format_processing_result(self, result: ProcessingResult, show_details: bool = False) -> str:
        """
        Format complete processing result.

        Args:
            result: Processing result to format
            show_details: Whether to show detailed information

        Returns:
            Formatted result string
        """
        output = []

        # Header
        header = "🍽️  Holiday Meal Planning Results"
        output.append(self._create_header(header))

        # Processing summary
        metadata = result.processing_metadata
        processing_time = metadata.total_processing_time_ms / 1000
        success_rate = metadata.success_rate * 100

        summary = f"✅ Processed {metadata.items_processed} items in {processing_time:.1f}s ({success_rate:.0f}% success rate)"
        output.append(f"\n{summary}")

        # Grocery list
        grocery_section = self.format_grocery_list(result.grocery_list, show_details)
        output.append(f"\n{grocery_section}")

        # Timeline (if available)
        if result.prep_timeline and result.prep_timeline.days:
            timeline_section = self.format_timeline(result.prep_timeline, compact=not show_details)
            output.append(f"\n{timeline_section}")

        # Failed items (if any)
        if result.failed_items:
            failed_section = self._format_failed_items(result.failed_items)
            output.append(f"\n{failed_section}")

        # Processing details (if requested)
        if show_details:
            details_section = self._format_processing_details(metadata, result.processed_items)
            output.append(f"\n{details_section}")

        return "\n".join(output)

    def format_error_message(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Format error messages for user display.

        Args:
            error: Exception to format
            context: Optional context information

        Returns:
            Formatted error message
        """
        output = []

        # Error header
        error_type = type(error).__name__
        output.append(f"❌ {error_type}")

        # Error message
        error_msg = str(error)
        wrapped_msg = self._wrap_text(error_msg, prefix="   ")
        output.append(wrapped_msg)

        # Context information
        if context:
            output.append("\n📝 Context:")
            for key, value in context.items():
                if key != "error" and value is not None:
                    formatted_value = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    output.append(f"   {key}: {formatted_value}")

        # Suggestions based on error type
        suggestions = self._get_error_suggestions(error)
        if suggestions:
            output.append("\n💡 Suggestions:")
            for suggestion in suggestions:
                wrapped_suggestion = self._wrap_text(suggestion, prefix="   • ")
                output.append(wrapped_suggestion)

        return "\n".join(output)

    def format_progress_summary(self, phase: str, current: int, total: int, item_name: str = "items") -> str:
        """
        Format progress summary for display.

        Args:
            phase: Current processing phase
            current: Current item number
            total: Total items to process
            item_name: Name of items being processed

        Returns:
            Formatted progress string
        """
        percentage = (current / total * 100) if total > 0 else 0
        progress_bar = self._create_progress_bar(current, total)

        return f"🔄 {phase}: {current}/{total} {item_name} {progress_bar} {percentage:.0f}%"

    # Helper methods for formatting

    def _create_header(self, text: str, style: str = "bold blue") -> str:
        """Create a formatted header."""
        return f"\n{text}\n{'=' * len(text)}"

    def _format_category_name(self, category: Optional[IngredientCategory]) -> str:
        """Format category name for display."""
        if not category:
            return get_text("categories.other")

        # Use localized category names that already include icons
        category_key = category.value if category else "other"
        return get_text(f"categories.{category_key}")

    def _format_ingredient(self, ingredient: Ingredient, show_details: bool = False) -> str:
        """Format individual ingredient for display."""
        # Format quantity
        quantity_str = self._format_quantity(ingredient.quantity)

        # Format unit
        unit_str = ingredient.unit.value.replace("_", " ")
        if unit_str == "to taste":
            unit_str = ""

        # Basic format
        if unit_str:
            formatted = f"□ {quantity_str} {unit_str} {ingredient.name}"
        else:
            formatted = f"□ {ingredient.name} (to taste)"

        # Add details if requested
        if show_details and ingredient.confidence < 0.8:
            confidence_str = self._format_confidence(ingredient.confidence)
            formatted += f" [{confidence_str}]"

        return formatted

    def _format_quantity(self, quantity: float) -> str:
        """Format quantity with appropriate precision."""
        if quantity == int(quantity):
            return str(int(quantity))

        # Handle common fractions
        fractions = {
            0.25: "¼", 0.33: "⅓", 0.5: "½", 0.67: "⅔", 0.75: "¾"
        }

        # Check if close to a common fraction
        for frac_val, frac_str in fractions.items():
            if abs(quantity - frac_val) < 0.01:
                return frac_str

        # Check for mixed numbers
        whole = int(quantity)
        fractional = quantity - whole

        if whole > 0 and fractional > 0:
            for frac_val, frac_str in fractions.items():
                if abs(fractional - frac_val) < 0.01:
                    return f"{whole} {frac_str}"

        # Default to decimal with reasonable precision
        if quantity < 10:
            return f"{quantity:.2f}".rstrip('0').rstrip('.')
        else:
            return f"{quantity:.1f}".rstrip('0').rstrip('.')

    def _format_confidence(self, confidence: float) -> str:
        """Format confidence score for display."""
        percentage = int(confidence * 100)
        if percentage >= 90:
            return f"✅ {percentage}%"
        elif percentage >= 70:
            return f"⚠️  {percentage}%"
        else:
            return f"❓ {percentage}%"

    def _group_by_category(self, ingredients: List[Ingredient]) -> Dict[Optional[IngredientCategory], List[Ingredient]]:
        """Group ingredients by category."""
        groups = {}

        # Define category order
        category_order = [
            IngredientCategory.PROTEIN,
            IngredientCategory.VEGETABLE,
            IngredientCategory.FRUIT,
            IngredientCategory.DAIRY,
            IngredientCategory.GRAIN,
            IngredientCategory.FAT,
            IngredientCategory.HERB,
            IngredientCategory.SPICE,
            IngredientCategory.OTHER,
            None  # Uncategorized
        ]

        # Group ingredients
        for ingredient in ingredients:
            category = ingredient.category
            if category not in groups:
                groups[category] = []
            groups[category].append(ingredient)

        # Sort within each category by name
        for category in groups:
            groups[category].sort(key=lambda ing: ing.name.lower())

        # Return in category order
        ordered_groups = {}
        for category in category_order:
            if category in groups:
                ordered_groups[category] = groups[category]

        return ordered_groups

    def _format_consolidation_notes(self, notes: List[str]) -> str:
        """Format consolidation notes for display."""
        if not notes:
            return ""

        output = [get_text("grocery_list.consolidation_notes")]
        for note in notes[:5]:  # Limit to first 5 notes
            wrapped_note = self._wrap_text(note, prefix="   • ")
            output.append(wrapped_note)

        if len(notes) > 5:
            output.append(f"   ... and {len(notes) - 5} more notes")

        return "\n".join(output)

    def _format_day_plan(self, day_plan: DayPlan, compact: bool = False) -> str:
        """Format day plan for display."""
        # Day header
        day_name = day_plan.date.strftime("%A, %B %d")
        if day_plan.day_offset == 0:
            day_header = f"🍽️  {day_name} (Day of Meal)"
        elif day_plan.day_offset == 1:
            day_header = f"📅 {day_name} (1 Day Before)"
        else:
            day_header = f"📅 {day_name} ({day_plan.day_offset} Days Before)"

        # Workload indicator
        workload_stars = "★" * day_plan.workload_level + "☆" * (5 - day_plan.workload_level)
        duration_hours = day_plan.total_duration // 60
        duration_minutes = day_plan.total_duration % 60

        header_info = f"   Workload: {workload_stars} ({day_plan.workload_level}/5)"
        if duration_hours > 0:
            header_info += f"  •  Duration: {duration_hours}h {duration_minutes}m"
        else:
            header_info += f"  •  Duration: {duration_minutes}m"

        output = [f"\n{day_header}", header_info]

        if not day_plan.tasks:
            output.append("   No specific tasks scheduled")
            return "\n".join(output)

        # Format tasks
        for i, task in enumerate(day_plan.tasks, 1):
            task_line = self._format_prep_task(task, i, compact)
            output.append(task_line)

        # Add notes if any
        if day_plan.notes:
            notes_line = self._wrap_text(day_plan.notes, prefix="   💡 ")
            output.append(notes_line)

        return "\n".join(output)

    def _format_prep_task(self, task: PrepTask, number: int, compact: bool = False) -> str:
        """Format preparation task for display."""
        duration_str = f"{task.estimated_duration}m"

        if compact:
            return f"   {number}. {task.task_description} ({duration_str})"
        else:
            timing_icon = {
                "make_ahead": "📦",
                "day_before": "🌙",
                "day_of_early": "🌅",
                "day_of_late": "🍳",
                "immediate": "⚡"
            }.get(task.timing_type.value, "⏰")

            formatted = f"   {number}. {timing_icon} {task.task_description}"
            formatted += f" ({duration_str}, {task.dish_name})"

            if task.dependencies:
                formatted += f" [depends on: {', '.join(task.dependencies)}]"

            return formatted

    def _format_failed_items(self, failed_items: List[Dict[str, Any]]) -> str:
        """Format failed items for display."""
        if not failed_items:
            return ""

        output = [f"⚠️  Failed to Process {len(failed_items)} Items:"]

        for item in failed_items:
            item_desc = item.get('source_url', item.get('description', 'Unknown item'))
            if len(item_desc) > 60:
                item_desc = item_desc[:57] + "..."

            error_msg = item.get('error_message', 'Unknown error')
            output.append(f"   • {item_desc}")
            output.append(f"     Error: {error_msg}")

            if item.get('retry_suggested', False):
                output.append("     💡 Retry suggested")

        return "\n".join(output)

    def _format_processing_details(self, metadata, processed_items: List) -> str:
        """Format processing details for display."""
        output = ["📊 Processing Details:"]

        # Timing information
        processing_seconds = metadata.total_processing_time_ms / 1000
        output.append(f"   Processing time: {processing_seconds:.1f} seconds")
        output.append(f"   Web requests made: {metadata.web_requests_made}")
        output.append(f"   Average confidence: {metadata.average_confidence:.0%}")

        # Per-item breakdown
        if processed_items:
            output.append(f"\n   Processed Items ({len(processed_items)}):")
            for item in processed_items[:3]:  # Show first 3 items
                title = item.extracted_title or "Unnamed Recipe"
                if len(title) > 40:
                    title = title[:37] + "..."
                time_ms = item.processing_time_ms
                ingredient_count = item.ingredients_count
                output.append(f"     • {title} ({ingredient_count} ingredients, {time_ms}ms)")

            if len(processed_items) > 3:
                output.append(f"     ... and {len(processed_items) - 3} more items")

        return "\n".join(output)

    def _get_error_suggestions(self, error: Exception) -> List[str]:
        """Get suggestions based on error type."""
        error_type = type(error).__name__

        suggestions_map = {
            'SecurityError': [
                "Ensure URLs use HTTPS protocol",
                "Check that the URL is from a trusted recipe site"
            ],
            'WebScrapingError': [
                "Verify the URL is accessible and contains a valid recipe",
                "Try a different recipe site if this one is having issues",
                "Check your internet connection"
            ],
            'RecipeParsingError': [
                "Try using a description instead of a URL",
                "Ensure the URL points to a recipe page (not a blog post or index)",
                "Some recipe sites may not be supported yet"
            ],
            'ValidationError': [
                "Check that all required fields are provided",
                "Verify serving size is reasonable (1-100 people)"
            ],
            'IngredientConsolidationError': [
                "Some ingredients may have conflicting units",
                "Try processing with a lower similarity threshold"
            ]
        }

        return suggestions_map.get(error_type, [
            "Please check your input and try again",
            "If the problem persists, try a different approach"
        ])

    def _wrap_text(self, text: str, width: int = 70, prefix: str = "") -> str:
        """Wrap text with prefix."""
        wrapped_lines = wrap(text, width=width - len(prefix))
        return "\n".join(prefix + line for line in wrapped_lines)

    def _create_progress_bar(self, current: int, total: int, width: int = 20) -> str:
        """Create a simple ASCII progress bar."""
        if total == 0:
            return "[" + " " * width + "]"

        progress = current / total
        filled = int(progress * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"


# Convenience functions for quick formatting

def format_grocery_list_simple(grocery_list: ConsolidatedGroceryList) -> str:
    """Format grocery list in simple text format."""
    formatter = CLIFormatter()
    return formatter.format_grocery_list(grocery_list, show_details=False)


def format_error_simple(error: Exception) -> str:
    """Format error in simple text format."""
    formatter = CLIFormatter()
    return formatter.format_error_message(error)


def format_timeline_table(self, timeline: Timeline) -> Table:
    """
    Format timeline as a rich table for better visualization.

    Args:
        timeline: Timeline to format

    Returns:
        Rich table with timeline data
    """
    table = Table(title="📅 Preparation Timeline", box=box.ROUNDED, show_header=True, header_style="bold blue")

    # Add columns
    table.add_column("Day", style="cyan", no_wrap=True)
    table.add_column("Date", style="green")
    table.add_column("Tasks", min_width=40)
    table.add_column("Duration", justify="right", style="yellow")
    table.add_column("Workload", justify="center")

    # Add rows for each day
    for day in timeline.days:
        day_name = day.date.strftime("%A")
        day_date = day.date.strftime("%b %d")

        # Format tasks list
        task_list = []
        for i, task in enumerate(day.tasks[:3], 1):  # Show first 3 tasks
            timing_icon = {
                "make_ahead": "📦",
                "day_before": "🌙",
                "day_of_early": "🌅",
                "day_of_late": "🍳",
                "immediate": "⚡"
            }.get(task.timing_type.value, "⏰")

            task_desc = task.task_description
            if len(task_desc) > 35:
                task_desc = task_desc[:32] + "..."

            task_list.append(f"{timing_icon} {task_desc}")

        if len(day.tasks) > 3:
            task_list.append(f"... and {len(day.tasks) - 3} more")

        tasks_text = "\n".join(task_list) if task_list else "No tasks"

        # Format duration
        hours = day.total_duration // 60
        minutes = day.total_duration % 60
        if hours > 0:
            duration_text = f"{hours}h {minutes}m"
        else:
            duration_text = f"{minutes}m"

        # Workload visualization
        workload_stars = "★" * day.workload_level + "☆" * (5 - day.workload_level)

        # Determine day description
        if day.day_offset == 0:
            day_desc = "Meal Day"
        elif day.day_offset == 1:
            day_desc = "1 Day Before"
        else:
            day_desc = f"{day.day_offset} Days Before"

        table.add_row(
            day_desc,
            f"{day_name}\n{day_date}",
            tasks_text,
            duration_text,
            f"{workload_stars}\n{day.workload_level}/5"
        )

    return table

    def format_timeline_summary(self, timeline: Timeline) -> str:
        """
        Format a concise timeline summary.

        Args:
            timeline: Timeline to summarize

        Returns:
            Formatted timeline summary
        """
        output = []

        # Header
        meal_date = timeline.meal_date.strftime("%A, %B %d")
        output.append(f"📅 Timeline Summary for {meal_date}")
        output.append("=" * (len(f"Timeline Summary for {meal_date}") + 2))

        # Key statistics
        total_days = len(timeline.days)
        total_tasks = sum(len(day.tasks) for day in timeline.days)
        avg_workload = sum(day.workload_level for day in timeline.days) / total_days if total_days > 0 else 0

        stats = [
            f"📊 {total_days} preparation days",
            f"✅ {total_tasks} total tasks",
            f"⭐ {avg_workload:.1f}/5 average workload",
            f"🕒 {timeline.total_prep_time // 60}h {timeline.total_prep_time % 60}m total time"
        ]

        output.extend(stats)
        output.append("")

        # Day-by-day summary
        output.append("📋 Day Summary:")
        for day in timeline.days:
            day_name = day.date.strftime("%a %m/%d")
            task_count = len(day.tasks)
            duration = f"{day.total_duration // 60}h{day.total_duration % 60:02d}m"
            workload = "★" * day.workload_level

            if day.day_offset == 0:
                day_prefix = "🍽️ "
            else:
                day_prefix = "📅 "

            summary_line = f"{day_prefix}{day_name}: {task_count} tasks, {duration}, {workload}"
            output.append(f"   {summary_line}")

        # Critical path info
        if timeline.critical_path:
            output.append("")
            output.append("🚨 Critical Path:")
            output.append(f"   {len(timeline.critical_path)} tasks must be completed on schedule")

        return "\n".join(output)

def print_grocery_list(grocery_list: ConsolidatedGroceryList, table_format: bool = True) -> None:
    """Print grocery list to console with rich formatting."""
    console = Console()
    formatter = CLIFormatter(console)

    if table_format:
        table = formatter.format_grocery_list_table(grocery_list)
        console.print(table)
    else:
        formatted = formatter.format_grocery_list(grocery_list)
        console.print(formatted)


def print_timeline(timeline: Timeline, table_format: bool = True) -> None:
    """Print timeline to console with rich formatting."""
    console = Console()
    formatter = CLIFormatter(console)

    if table_format:
        table = formatter.format_timeline_table(timeline)
        console.print(table)
    else:
        formatted = formatter.format_timeline(timeline)
        console.print(formatted)