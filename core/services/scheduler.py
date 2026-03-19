"""
Task dependency analyzer for Holiday Meal Planner.

Implements topological sorting with NetworkX, food safety constraints,
critical path analysis for optimal preparation scheduling.
"""

import logging
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

import networkx as nx

from core.models import PrepTask, TimingType
from shared.exceptions import MealPlannerException

logger = logging.getLogger(__name__)


class SchedulingError(MealPlannerException):
    """Raised when task scheduling fails."""
    pass


@dataclass
class TaskNode:
    """Represents a task node in the dependency graph."""
    task: PrepTask
    earliest_start: int = 0  # Minutes from meal time (negative = before meal)
    latest_start: int = 0
    slack: int = 0
    is_critical: bool = False


class TaskDependencyAnalyzer:
    """
    Analyzes task dependencies and generates optimal scheduling.

    Uses topological sorting with NetworkX for dependency resolution,
    incorporates food safety constraints, and performs critical path analysis.
    """

    # Food safety timing constraints (minutes before meal time)
    FOOD_SAFETY_CONSTRAINTS = {
        TimingType.MAKE_AHEAD: (-7 * 24 * 60, -48 * 60),  # 7 days to 2 days before
        TimingType.DAY_BEFORE: (-48 * 60, -12 * 60),      # 2 days to 12 hours before
        TimingType.DAY_OF_EARLY: (-12 * 60, -4 * 60),     # 12 to 4 hours before
        TimingType.DAY_OF_LATE: (-4 * 60, -30),           # 4 hours to 30 minutes before
        TimingType.IMMEDIATE: (-30, 0),                    # 30 minutes before to meal time
    }

    def __init__(self):
        """Initialize the task dependency analyzer."""
        self.dependency_graph = nx.DiGraph()
        self.task_nodes: Dict[str, TaskNode] = {}

    def build_dependency_graph(self, tasks: List[PrepTask]) -> None:
        """
        Build a directed acyclic graph of task dependencies.

        Args:
            tasks: List of preparation tasks to schedule

        Raises:
            SchedulingError: If circular dependencies are detected
        """
        logger.info(f"Building dependency graph for {len(tasks)} tasks")

        # Clear previous graph
        self.dependency_graph.clear()
        self.task_nodes.clear()

        # Add nodes for all tasks
        for task in tasks:
            self.dependency_graph.add_node(task.id)
            self.task_nodes[task.id] = TaskNode(task=task)

        # Add edges for dependencies
        for task in tasks:
            for dependency_id in task.dependencies:
                if dependency_id not in self.task_nodes:
                    logger.warning(f"Task {task.id} depends on unknown task {dependency_id}")
                    continue

                # Add edge from dependency to dependent task
                self.dependency_graph.add_edge(dependency_id, task.id)

        # Check for cycles
        if not nx.is_directed_acyclic_graph(self.dependency_graph):
            cycles = list(nx.simple_cycles(self.dependency_graph))
            raise SchedulingError(f"Circular dependencies detected: {cycles}")

        logger.info("Dependency graph built successfully")

    def apply_food_safety_constraints(self) -> None:
        """Apply food safety timing constraints to tasks."""
        logger.info("Applying food safety constraints")

        for task_id, node in self.task_nodes.items():
            timing_type = node.task.timing_type

            if timing_type in self.FOOD_SAFETY_CONSTRAINTS:
                min_time, max_time = self.FOOD_SAFETY_CONSTRAINTS[timing_type]

                # Set initial timing constraints
                node.earliest_start = min_time
                node.latest_start = max_time - node.task.estimated_duration

                logger.debug(
                    f"Task {task_id} ({timing_type.value}): "
                    f"earliest={min_time}, latest={node.latest_start}"
                )

    def calculate_critical_path(self) -> List[str]:
        """
        Calculate critical path using forward and backward pass.

        Returns:
            List of task IDs on the critical path
        """
        logger.info("Calculating critical path")

        # Forward pass: calculate earliest start times
        for task_id in nx.topological_sort(self.dependency_graph):
            node = self.task_nodes[task_id]

            # Consider dependencies
            predecessors = list(self.dependency_graph.predecessors(task_id))
            if predecessors:
                max_predecessor_finish = max(
                    self.task_nodes[pred_id].earliest_start +
                    self.task_nodes[pred_id].task.estimated_duration
                    for pred_id in predecessors
                )
                # Ensure we don't violate food safety constraints
                node.earliest_start = max(node.earliest_start, max_predecessor_finish)

        # Backward pass: calculate latest start times
        for task_id in reversed(list(nx.topological_sort(self.dependency_graph))):
            node = self.task_nodes[task_id]

            # Consider successors
            successors = list(self.dependency_graph.successors(task_id))
            if successors:
                min_successor_start = min(
                    self.task_nodes[succ_id].latest_start
                    for succ_id in successors
                )
                task_finish_time = min_successor_start
                node.latest_start = min(
                    node.latest_start,
                    task_finish_time - node.task.estimated_duration
                )

        # Calculate slack and identify critical tasks
        critical_path = []
        for task_id, node in self.task_nodes.items():
            node.slack = node.latest_start - node.earliest_start
            node.is_critical = node.slack <= 0

            if node.is_critical:
                critical_path.append(task_id)

        logger.info(f"Critical path identified: {len(critical_path)} tasks")
        return critical_path

    def get_topological_order(self) -> List[str]:
        """
        Get tasks in topological order (dependency-respecting sequence).

        Returns:
            List of task IDs in dependency order
        """
        try:
            return list(nx.topological_sort(self.dependency_graph))
        except nx.NetworkXError as e:
            raise SchedulingError(f"Failed to compute topological order: {e}")

    def validate_scheduling_feasibility(self) -> Dict[str, List[str]]:
        """
        Validate that the schedule is feasible given constraints.

        Returns:
            Dictionary of constraint violations by category
        """
        violations = {
            'timing_conflicts': [],
            'dependency_violations': [],
            'food_safety_violations': [],
            'workload_warnings': []
        }

        # Check timing conflicts
        for task_id, node in self.task_nodes.items():
            if node.earliest_start > node.latest_start:
                violations['timing_conflicts'].append(
                    f"Task {task_id}: impossible timing window "
                    f"(earliest: {node.earliest_start}, latest: {node.latest_start})"
                )

        # Check dependency satisfaction
        for task_id in self.dependency_graph.nodes():
            node = self.task_nodes[task_id]
            task_start = node.earliest_start

            for pred_id in self.dependency_graph.predecessors(task_id):
                pred_node = self.task_nodes[pred_id]
                pred_finish = pred_node.earliest_start + pred_node.task.estimated_duration

                if pred_finish > task_start:
                    violations['dependency_violations'].append(
                        f"Task {task_id} starts before dependency {pred_id} finishes"
                    )

        # Check food safety constraints
        for task_id, node in self.task_nodes.items():
            timing_type = node.task.timing_type
            if timing_type in self.FOOD_SAFETY_CONSTRAINTS:
                min_time, max_time = self.FOOD_SAFETY_CONSTRAINTS[timing_type]
                task_start = node.earliest_start
                task_end = task_start + node.task.estimated_duration

                if task_start < min_time or task_end > max_time:
                    violations['food_safety_violations'].append(
                        f"Task {task_id} violates {timing_type.value} timing constraints"
                    )

        return violations

    def optimize_workload_distribution(self, max_daily_hours: int = 4) -> Dict[int, List[str]]:
        """
        Distribute tasks across days to balance workload.

        Args:
            max_daily_hours: Maximum hours of work per day

        Returns:
            Dictionary mapping day offset to list of task IDs
        """
        logger.info(f"Optimizing workload distribution (max {max_daily_hours}h/day)")

        max_daily_minutes = max_daily_hours * 60
        daily_schedule: Dict[int, List[str]] = {}

        # Sort tasks by earliest start time
        sorted_tasks = sorted(
            self.task_nodes.items(),
            key=lambda x: x[1].earliest_start
        )

        for task_id, node in sorted_tasks:
            task_duration = node.task.estimated_duration

            # Calculate day offset from meal (negative = days before)
            task_start_hours = node.earliest_start / 60.0
            target_day = int(abs(task_start_hours) / 24)

            # Find a day with sufficient capacity
            day_found = False
            for day_offset in range(target_day, target_day + 3):  # Try up to 3 days earlier
                if day_offset not in daily_schedule:
                    daily_schedule[day_offset] = []

                # Calculate current day load
                current_load = sum(
                    self.task_nodes[tid].task.estimated_duration
                    for tid in daily_schedule[day_offset]
                )

                if current_load + task_duration <= max_daily_minutes:
                    daily_schedule[day_offset].append(task_id)
                    day_found = True
                    break

            if not day_found:
                # Force schedule on target day and warn about overload
                if target_day not in daily_schedule:
                    daily_schedule[target_day] = []
                daily_schedule[target_day].append(task_id)
                logger.warning(f"Day {target_day} overloaded by task {task_id}")

        return daily_schedule

    def get_scheduling_summary(self) -> Dict[str, any]:
        """Get a summary of the scheduling analysis."""
        total_duration = sum(
            node.task.estimated_duration
            for node in self.task_nodes.values()
        )

        critical_tasks = [
            task_id for task_id, node in self.task_nodes.items()
            if node.is_critical
        ]

        return {
            'total_tasks': len(self.task_nodes),
            'total_duration_minutes': total_duration,
            'total_duration_hours': round(total_duration / 60.0, 1),
            'critical_tasks_count': len(critical_tasks),
            'critical_tasks': critical_tasks,
            'has_violations': bool(self.validate_scheduling_feasibility()),
            'latest_start_time': min(
                node.latest_start for node in self.task_nodes.values()
            ) if self.task_nodes else 0
        }