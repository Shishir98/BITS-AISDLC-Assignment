from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import Task


@runtime_checkable
class TaskRepository(Protocol):
    def load(self) -> tuple[list[Task], int]:
        """Return the task list and the next identifier to allocate."""

    def save(self, tasks: list[Task], next_id: int) -> None:
        """Persist a complete task snapshot and next id."""
