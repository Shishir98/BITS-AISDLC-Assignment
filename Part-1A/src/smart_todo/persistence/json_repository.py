from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..domain.models import Task
from ..domain.ports import TaskRepository
from .errors import MalformedStoredDataError, PersistenceError, StoreWriteError

_LOGGER = logging.getLogger(__name__)


class DuplicateMemberError(ValueError):
    """Raised when a JSON object contains a duplicate member name."""


class JsonTaskRepository(TaskRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._requires_recovery = False

    def load(self) -> tuple[list[Task], int]:
        self._ensure_recovered()
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
        self._ensure_recovered()
        artifacts: list[Path] = []
        backup: Path | None = None
        original_bytes: bytes | None = None
        original_captured = False
        try:
            candidate = self._serialize_candidate(tasks, next_id)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                original_bytes = self.path.read_bytes()
            except FileNotFoundError:
                original_bytes = None
            original_captured = True

            if original_bytes is not None:
                backup = self._write_artifact(original_bytes, ".recovery.", ".bak", artifacts)
                if backup.read_bytes() != original_bytes:
                    raise OSError("Recovery backup verification failed")

            candidate_path = self._write_artifact(candidate, ".", ".tmp", artifacts)
            os.replace(candidate_path, self.path)
            artifacts.remove(candidate_path)
            if self.path.read_bytes() != candidate:
                raise OSError("Primary store verification failed")
        except Exception as exc:
            recovered = True
            if original_captured:
                recovered = self._restore_previous_store(original_bytes, backup, artifacts)
            if recovered:
                self._cleanup_artifacts(artifacts)
            else:
                self._requires_recovery = True
                _LOGGER.error("Task store recovery could not be verified; repository is fail-closed")
            raise StoreWriteError("Could not persist tasks to disk") from exc
        self._cleanup_artifacts(artifacts)

    def _ensure_recovered(self) -> None:
        if self._requires_recovery:
            raise StoreWriteError("Task store requires recovery")

    def _serialize_candidate(self, tasks: list[Task], next_id: int) -> bytes:
        document = {
            "next_id": next_id,
            "tasks": [task.model_dump_for_store() for task in sorted(tasks, key=lambda item: item.id)],
        }
        return json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _write_artifact(
        self,
        contents: bytes,
        prefix: str,
        suffix: str,
        artifacts: list[Path],
    ) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(self.path.parent),
            prefix=f".{self.path.name}{prefix}",
            suffix=suffix,
            delete=False,
        ) as handle:
            artifact = Path(handle.name)
            artifacts.append(artifact)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        return artifact

    def _restore_previous_store(
        self,
        original_bytes: bytes | None,
        backup: Path | None,
        artifacts: list[Path],
    ) -> bool:
        if original_bytes is None:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                return self._is_absent()
            return self._is_absent()

        if backup is None:
            return self._matches_primary(original_bytes)
        try:
            backup_bytes = backup.read_bytes()
            if backup_bytes != original_bytes:
                return self._matches_primary(original_bytes)
            if self._matches_primary(original_bytes):
                return True
            restore_path = self._write_artifact(backup_bytes, ".restore.", ".tmp", artifacts)
            if restore_path.read_bytes() != original_bytes:
                return False
            os.replace(restore_path, self.path)
            artifacts.remove(restore_path)
            return self.path.read_bytes() == original_bytes
        except OSError:
            return self._matches_primary(original_bytes)

    def _matches_primary(self, expected: bytes) -> bool:
        try:
            return self.path.read_bytes() == expected
        except OSError:
            return False

    def _is_absent(self) -> bool:
        try:
            self.path.stat()
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return False

    @staticmethod
    def _cleanup_artifacts(artifacts: list[Path]) -> None:
        for artifact in artifacts:
            try:
                artifact.unlink(missing_ok=True)
            except OSError:
                _LOGGER.warning("Could not clean up a task store transaction artifact")

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
