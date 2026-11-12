from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence

from .errors import InvalidStatusTransitionError, TaskNotFoundError, TaskValidationError
from .models import Priority, Task, TaskStatus
from .ports import TaskRepository

_UNSET = object()


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository
        self._lock = threading.RLock()
        self._tasks: dict[int, Task] = {}
        self._next_id = 1
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            tasks, next_id = self._repository.load()
            self._tasks = {task.id: task for task in tasks}
            self._next_id = next_id
            self._loaded = True

    def list_tasks(self, tags: Sequence[str] | None = None, sort: str | None = None) -> list[Task]:
        with self._lock:
            self._ensure_loaded()
            filtered = list(self._tasks.values())
            requested = normalize_filters(tags)
            if requested:
                filtered = [task for task in filtered if requested.issubset(set(task.tags))]
            if sort == "priority":
                filtered.sort(key=lambda task: (priority_rank(task.priority), task.id))
            else:
                filtered.sort(key=lambda task: task.id)
            return [task.model_copy(deep=True) for task in filtered]

    def get_task(self, task_id: int) -> Task:
        with self._lock:
            self._ensure_loaded()
            try:
                return self._tasks[task_id].model_copy(deep=True)
            except KeyError as exc:
                raise TaskNotFoundError(f"Task {task_id} not found") from exc

    def create_task(self, title: str, description: str | None, tags: Sequence[str] | None, priority: Priority | None) -> Task:
        with self._lock:
            self._ensure_loaded()
            cleaned_title = normalize_title(title)
            cleaned_tags = normalize_tags(tags)
            task = Task(
                id=self._next_id,
                title=cleaned_title,
                description=description,
                tags=list(cleaned_tags),
                priority=priority or Priority.MEDIUM,
                status=TaskStatus.PENDING,
            )
            candidate_tasks = dict(self._tasks)
            candidate_tasks[task.id] = task
            candidate_next_id = self._next_id + 1
            self._repository.save(sorted(candidate_tasks.values(), key=lambda item: item.id), candidate_next_id)
            self._tasks = candidate_tasks
            self._next_id = candidate_next_id
            return task.model_copy(deep=True)

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None | object = _UNSET,
        description: str | None | object = _UNSET,
        tags: Sequence[str] | None | object = _UNSET,
        priority: Priority | None | object = _UNSET,
    ) -> Task:
        with self._lock:
            self._ensure_loaded()
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"Task {task_id} not found")
            current = self._tasks[task_id]
            updates: dict[str, object] = {}
            if title is not _UNSET:
                updates["title"] = normalize_title(title) if title is not None else None
            if description is not _UNSET:
                updates["description"] = description
            if tags is not _UNSET:
                updates["tags"] = list(normalize_tags(tags)) if tags is not None else []
            if priority is not _UNSET:
                updates["priority"] = priority
            if not updates:
                raise TaskValidationError("At least one field must be provided")
            candidate = current.model_copy(update=updates)
            candidate_tasks = dict(self._tasks)
            candidate_tasks[task_id] = candidate
            self._repository.save(sorted(candidate_tasks.values(), key=lambda item: item.id), self._next_id)
            self._tasks = candidate_tasks
            return candidate.model_copy(deep=True)

    def delete_task(self, task_id: int) -> None:
        with self._lock:
            self._ensure_loaded()
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"Task {task_id} not found")
            candidate_tasks = dict(self._tasks)
            del candidate_tasks[task_id]
            self._repository.save(sorted(candidate_tasks.values(), key=lambda item: item.id), self._next_id)
            self._tasks = candidate_tasks

    def update_status(self, task_id: int, status: TaskStatus) -> Task:
        with self._lock:
            self._ensure_loaded()
            if task_id not in self._tasks:
                raise TaskNotFoundError(f"Task {task_id} not found")
            current = self._tasks[task_id]
            if status == current.status:
                return current.model_copy(deep=True)
            allowed = {
                (TaskStatus.PENDING, TaskStatus.IN_PROGRESS),
                (TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED),
            }
            if (current.status, status) not in allowed:
                raise InvalidStatusTransitionError(f"Status transition from {current.status.value} to {status.value} is not allowed")
            candidate = current.model_copy(update={"status": status})
            candidate_tasks = dict(self._tasks)
            candidate_tasks[task_id] = candidate
            self._repository.save(sorted(candidate_tasks.values(), key=lambda item: item.id), self._next_id)
            self._tasks = candidate_tasks
            return candidate.model_copy(deep=True)


def normalize_title(value: str) -> str:
    cleaned = value.strip()
    if not 1 <= len(cleaned) <= 200:
        raise TaskValidationError("title must be 1-200 characters after trimming")
    return cleaned


def normalize_tags(values: Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        tag = raw.strip().lower()
        if not 1 <= len(tag) <= 32:
            raise TaskValidationError("tag values must be 1-32 characters after normalization")
        if tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    return sorted(cleaned)


def normalize_filters(tags: Sequence[str] | None) -> set[str]:
    if not tags:
        return set()
    return set(normalize_tags(tags))


def priority_rank(value: Priority) -> int:
    order = {
        Priority.HIGH: 0,
        Priority.MEDIUM: 1,
        Priority.LOW: 2,
    }
    return order.get(value, 99)
