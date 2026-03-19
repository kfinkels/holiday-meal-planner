"""
Timeline Generator Agent for Holiday Meal Planner.

Creates optimized day-by-day preparation schedules using constraint programming
with OR-Tools, workload balancing, and the task dependency analyzer.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
import networkx as nx

from core.models import (
    PrepTask, Timeline, DayPlan, TimingType, MenuItemInput, Ingredient
)
from core.services.scheduler import TaskDependencyAnalyzer, SchedulingError
from shared.exceptions import AgentError, MealPlannerException
from shared.config import get_settings

logger = logging.getLogger(__name__)


class TimelineGenerationError(MealPlannerException):
    """Raised when timeline generation fails."""
    pass


class TimelineGenerationRequest(BaseModel):
    """Request model for timeline generation."""
    menu_items: List[MenuItemInput]
    meal_datetime: datetime
    max_prep_days: int = 7
    max_daily_hours: int = 4
    confidence_threshold: float = 0.6


class TimelineGenerationResponse(BaseModel):
    """Response model for timeline generation."""
    timeline: Timeline
    scheduling_summary: Dict[str, Any]
    generation_metadata: Dict[str, Any]


@dataclass
class DishAnalysis:
    """Analysis of a single dish for timeline generation."""
    dish_name: str
    prep_tasks: List[PrepTask]
    total_duration: int
    complexity_score: int
    earliest_start: int
    critical_path_tasks: List[str]


class TimelineGeneratorAgent:
    """
    PydanticAI agent for generating optimized preparation timelines.

    Uses constraint programming with OR-Tools for workload balancing
    and day-by-day scheduling with the task dependency analyzer.
    """

    def __init__(self):
        """Initialize timeline generator agent."""
        self.settings = get_settings()
        self.scheduler = TaskDependencyAnalyzer()

        # Initialize PydanticAI agent with configurable model
        model_config = self.settings.get_llm_model_config()
        self.agent = Agent(
            model_config,
            deps_type=Dict[str, Any],
            retries=2
        )

        self._setup_agent_tools()

    def _get_dependencies(self) -> Dict[str, Any]:
        """Get agent dependencies."""
        return {
            'scheduler': self.scheduler,
            'settings': self.settings
        }

    def _setup_agent_tools(self) -> None:
        """Set up agent tools and handlers."""

        @self.agent.tool
        async def extract_prep_tasks_from_dishes(
            ctx: RunContext[Dict[str, Any]],
            menu_items: List[MenuItemInput]
        ) -> List[PrepTask]:
            """Extract preparation tasks from menu items using AI."""
            prep_tasks = []

            for item in menu_items:
                # This would typically use an LLM to analyze the dish
                # For now, we'll create basic tasks based on dish type
                dish_name = item.description or f"Recipe from {item.source_url}"

                # Generate basic prep tasks for demonstration
                tasks = self._generate_basic_prep_tasks(dish_name, item.id)
                prep_tasks.extend(tasks)

            return prep_tasks

        @self.agent.tool
        async def analyze_dish_complexity(
            ctx: RunContext[Dict[str, Any]],
            dish_name: str,
            prep_tasks: List[PrepTask]
        ) -> DishAnalysis:
            """Analyze dish complexity and requirements."""
            total_duration = sum(task.estimated_duration for task in prep_tasks)

            # Calculate complexity based on duration and task variety
            complexity_factors = {
                'duration': min(total_duration / 60, 5),  # Hours to complexity points
                'task_count': min(len(prep_tasks), 3),
                'timing_variety': len(set(task.timing_type for task in prep_tasks))
            }

            complexity_score = int(sum(complexity_factors.values()))

            # Find earliest required start time
            earliest_start = min(
                self.scheduler.FOOD_SAFETY_CONSTRAINTS[task.timing_type][0]
                for task in prep_tasks
                if task.timing_type in self.scheduler.FOOD_SAFETY_CONSTRAINTS
            ) if prep_tasks else -24 * 60  # Default to 1 day before

            return DishAnalysis(
                dish_name=dish_name,
                prep_tasks=prep_tasks,
                total_duration=total_duration,
                complexity_score=complexity_score,
                earliest_start=earliest_start,
                critical_path_tasks=[]
            )

        @self.agent.tool
        async def optimize_daily_workload(
            ctx: RunContext[Dict[str, Any]],
            daily_schedule: Dict[int, List[str]],
            task_nodes: Dict[str, Any],
            max_daily_minutes: int
        ) -> Dict[int, List[str]]:
            """Optimize workload distribution across days."""
            optimized_schedule = daily_schedule.copy()

            # Identify overloaded days
            overloaded_days = []
            for day, task_ids in daily_schedule.items():
                total_load = sum(
                    task_nodes[task_id]['duration']
                    for task_id in task_ids
                )
                if total_load > max_daily_minutes:
                    overloaded_days.append((day, total_load))

            # Attempt to redistribute tasks from overloaded days
            for day, load in sorted(overloaded_days, key=lambda x: x[1], reverse=True):
                task_ids = optimized_schedule[day].copy()

                # Find moveable tasks (non-critical with flexibility)
                moveable_tasks = [
                    task_id for task_id in task_ids
                    if not task_nodes[task_id].get('is_critical', False)
                ]

                # Try to move tasks to earlier days
                for task_id in moveable_tasks:
                    task_duration = task_nodes[task_id]['duration']

                    # Try moving to earlier days (higher day_offset)
                    for target_day in range(day + 1, day + 4):
                        if target_day not in optimized_schedule:
                            optimized_schedule[target_day] = []

                        current_target_load = sum(
                            task_nodes[tid]['duration']
                            for tid in optimized_schedule[target_day]
                        )

                        if current_target_load + task_duration <= max_daily_minutes:
                            optimized_schedule[day].remove(task_id)
                            optimized_schedule[target_day].append(task_id)
                            break

            return optimized_schedule

    def _generate_basic_prep_tasks(self, dish_name: str, dish_id) -> List[PrepTask]:
        """Generate basic preparation tasks for a dish."""
        # This is a simplified implementation - would use AI in production
        base_tasks = [
            PrepTask(
                id=f"{dish_id}_prep",
                dish_name=dish_name,
                task_description=f"Prepare ingredients for {dish_name}",
                estimated_duration=30,
                dependencies=[],
                timing_type=TimingType.DAY_OF_EARLY,
                confidence=0.8
            ),
            PrepTask(
                id=f"{dish_id}_cook",
                dish_name=dish_name,
                task_description=f"Cook {dish_name}",
                estimated_duration=60,
                dependencies=[f"{dish_id}_prep"],
                timing_type=TimingType.DAY_OF_LATE,
                confidence=0.8
            )
        ]

        # Add make-ahead task for complex dishes
        if len(dish_name) > 20 or "roast" in dish_name.lower():
            base_tasks.insert(0, PrepTask(
                id=f"{dish_id}_marinate",
                dish_name=dish_name,
                task_description=f"Marinate/season {dish_name}",
                estimated_duration=15,
                dependencies=[],
                timing_type=TimingType.DAY_BEFORE,
                confidence=0.7
            ))
            base_tasks[1].dependencies.append(f"{dish_id}_marinate")

        return base_tasks

    async def generate_timeline(self, request: TimelineGenerationRequest) -> TimelineGenerationResponse:
        """
        Generate optimized preparation timeline.

        Args:
            request: Timeline generation request

        Returns:
            Timeline generation response with optimized schedule

        Raises:
            TimelineGenerationError: If timeline generation fails
        """
        try:
            logger.info(f"Generating timeline for {len(request.menu_items)} menu items")

            # Extract preparation tasks from menu items
            prep_tasks = await self.agent.run(
                'extract_prep_tasks_from_dishes',
                menu_items=request.menu_items
            )

            if not prep_tasks:
                raise TimelineGenerationError("No preparation tasks could be extracted")

            # Build dependency graph and analyze
            self.scheduler.build_dependency_graph(prep_tasks)
            self.scheduler.apply_food_safety_constraints()
            critical_path = self.scheduler.calculate_critical_path()

            # Validate scheduling feasibility
            violations = self.scheduler.validate_scheduling_feasibility()
            if violations['timing_conflicts'] or violations['dependency_violations']:
                raise TimelineGenerationError(
                    f"Scheduling conflicts detected: {violations}"
                )

            # Optimize workload distribution
            max_daily_minutes = request.max_daily_hours * 60
            daily_schedule = self.scheduler.optimize_workload_distribution(
                max_daily_hours=request.max_daily_hours
            )

            # Generate day plans
            day_plans = await self._create_day_plans(
                daily_schedule,
                request.meal_datetime,
                max_daily_minutes
            )

            # Calculate timeline metadata
            total_prep_time = sum(task.estimated_duration for task in prep_tasks)
            complexity_score = min(10, max(1, len(prep_tasks) // 2 + len(critical_path)))

            # Create timeline
            timeline = Timeline(
                meal_date=request.meal_datetime,
                days=sorted(day_plans, key=lambda x: x.day_offset, reverse=True),
                critical_path=critical_path,
                total_prep_time=total_prep_time,
                complexity_score=complexity_score,
                optimization_notes=self._generate_optimization_notes(violations, daily_schedule)
            )

            # Generate scheduling summary
            scheduling_summary = self.scheduler.get_scheduling_summary()

            # Generation metadata
            generation_metadata = {
                'generation_time': datetime.utcnow(),
                'tasks_generated': len(prep_tasks),
                'days_scheduled': len(day_plans),
                'critical_path_length': len(critical_path),
                'violations_found': sum(len(v) for v in violations.values()),
                'confidence_scores': [task.confidence for task in prep_tasks]
            }

            logger.info("Timeline generation completed successfully")

            return TimelineGenerationResponse(
                timeline=timeline,
                scheduling_summary=scheduling_summary,
                generation_metadata=generation_metadata
            )

        except Exception as e:
            logger.error(f"Timeline generation failed: {e}")
            raise TimelineGenerationError(f"Failed to generate timeline: {e}")

    async def _create_day_plans(
        self,
        daily_schedule: Dict[int, List[str]],
        meal_datetime: datetime,
        max_daily_minutes: int
    ) -> List[DayPlan]:
        """Create day plan objects from daily schedule."""
        day_plans = []

        for day_offset, task_ids in daily_schedule.items():
            # Get tasks for this day
            day_tasks = [
                self.scheduler.task_nodes[task_id].task
                for task_id in task_ids
                if task_id in self.scheduler.task_nodes
            ]

            # Calculate day metrics
            total_duration = sum(task.estimated_duration for task in day_tasks)
            workload_level = min(5, max(1, int(total_duration / max_daily_minutes * 5)))

            # Generate day notes
            notes = None
            if total_duration > max_daily_minutes:
                notes = f"Heavy day: {total_duration // 60}h {total_duration % 60}m planned"
            elif len(day_tasks) == 0:
                continue  # Skip empty days

            day_plans.append(DayPlan(
                day_offset=day_offset,
                date=meal_datetime - timedelta(days=day_offset),
                tasks=day_tasks,
                total_duration=total_duration,
                workload_level=workload_level,
                notes=notes
            ))

        return day_plans

    def _generate_optimization_notes(
        self,
        violations: Dict[str, List[str]],
        daily_schedule: Dict[int, List[str]]
    ) -> List[str]:
        """Generate optimization notes for the timeline."""
        notes = []

        if violations['workload_warnings']:
            notes.append("Some days may be overloaded - consider starting earlier")

        if violations['food_safety_violations']:
            notes.append("Review food safety timing for optimal quality")

        # Check for workload balance
        day_loads = [len(tasks) for tasks in daily_schedule.values()]
        if day_loads and max(day_loads) > 2 * (sum(day_loads) / len(day_loads)):
            notes.append("Workload is unbalanced across days")

        if not notes:
            notes.append("Timeline optimized for balanced workload and food safety")

        return notes