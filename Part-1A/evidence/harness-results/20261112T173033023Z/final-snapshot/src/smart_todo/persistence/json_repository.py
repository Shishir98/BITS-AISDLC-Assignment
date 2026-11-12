from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..domain.models import Task
from ..domain.ports import TaskRepository
from .errors import MalformedStoredDataError, PersistenceError, StoreWriteError


class DuplicateMemberError(ValueError):
    """Raised when a JSON object contains a duplicate member name."""


class JsonTaskRepository(TaskRepository):
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> tuple[list[Task], int]:
        if not self.path.exists():
            return [], 1
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise PersistenceError("Unable to read task store") from exc
        if not raw:
            raise MalformedStoredDataError("Stored JSON is empty")
        try:
            payload = json.loads(raw.decode("utf-8"), object_pairs_hook=self._reject_duplicate_members)
        except DuplicateMemberError as exc:
            raise MalformedStoredDataError("Stored JSON contains duplicate members") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedStoredDataError("Stored JSON is malformed") from exc
        return self._validate_document(payload)

    def save(self, tasks: list[Task], next_id: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "next_id": next_id,
            "tasks": [task.model_dump_for_store() for task in sorted(tasks, key=lambda item: item.id)],
        }
        payload = json.dumps(document, separators=(",", ":"), ensure_ascii=False)
        candidate = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.path.parent),
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                candidate = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(candidate, self.path)
        except OSError as exc:
            if candidate is not None and candidate.exists():
                candidate.unlink(missing_ok=True)
            raise StoreWriteError("Could not persist tasks to disk") from exc
        except Exception as exc:
            if candidate is not None and candidate.exists():
                candidate.unlink(missing_ok=True)
            raise PersistenceError("Failed to persist tasks") from exc
        else:
            if candidate is not None and candidate.exists():
                candidate.unlink(missing_ok=True)

    @staticmethod
    def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in seen:
                raise DuplicateMemberError(f"Duplicate member name: {key}")
            seen.add(key)
            result[key] = value
        return result

    @staticmethod
    def _validate_document(payload: Any) -> tuple[list[Task], int]:
        if not isinstance(payload, dict):
            raise MalformedStoredDataError("Stored document must be a JSON object")
        if set(payload.keys()) != {"next_id", "tasks"}:
            raise MalformedStoredDataError("Stored document must contain exactly next_id and tasks")
        next_id = payload["next_id"]
        tasks = payload["tasks"]
        if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id <= 0:
            raise MalformedStoredDataError("next_id must be a positive integer")
        if not isinstance(tasks, list):
            raise MalformedStoredDataError("tasks must be an array")
        validated_tasks: list[Task] = []
        seen_ids: set[int] = set()
        for entry in tasks:
            if not isinstance(entry, dict):
                raise MalformedStoredDataError("Each task must be an object")
            if set(entry.keys()) != {"id", "title", "description", "tags", "priority", "status"}:
                raise MalformedStoredDataError("Task fields are invalid")
            try:
                task = Task.model_validate(entry)
            except ValidationError as exc:
                raise MalformedStoredDataError("Task payload is invalid") from exc
            if task.id in seen_ids:
                raise MalformedStoredDataError("Duplicate task ids are not allowed")
            seen_ids.add(task.id)
            validated_tasks.append(task)
        max_id = max((task.id for task in validated_tasks), default=0)
        if next_id <= max_id:
            raise MalformedStoredDataError("next_id must be greater than every task id")
        return validated_tasks, next_id
