"""Benchmark tasks package."""

from bench.tasks.base import BenchTask
from bench.tasks.registry import TASKS, get_all_tasks, get_task_by_id

__all__ = ["BenchTask", "TASKS", "get_all_tasks", "get_task_by_id"]
