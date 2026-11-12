from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TaskStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: int = Field(ge=1)
    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("id must be a positive integer")
        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("title must be a string")
        cleaned = value.strip()
        if not 1 <= len(cleaned) <= 200:
            raise ValueError("title must be 1-200 characters after trimming")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("description must be a string or null")
        if len(value) > 2000:
            raise ValueError("description must be at most 2000 characters")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise TypeError("tags must be a list")
        if len(value) > 20:
            raise ValueError("tags must contain at most 20 entries")
        cleaned: list[str] = []
        seen: set[str] = set()
        for tag in value:
            if not isinstance(tag, str):
                raise TypeError("tag values must be strings")
            normalized = tag.strip().lower()
            if not 1 <= len(normalized) <= 32:
                raise ValueError("tag values must be 1-32 characters after normalization")
            if normalized not in seen:
                seen.add(normalized)
                cleaned.append(normalized)
        return sorted(cleaned)

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, value: Priority | str) -> Priority:
        if isinstance(value, Priority):
            return value
        if not isinstance(value, str):
            raise TypeError("priority must be a string")
        try:
            return Priority(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("priority must be Low, Medium, or High") from exc

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: TaskStatus | str) -> TaskStatus:
        if isinstance(value, TaskStatus):
            return value
        if not isinstance(value, str):
            raise TypeError("status must be a string")
        try:
            return TaskStatus(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("status must be Pending, In Progress, or Completed") from exc

    def model_dump_for_store(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tags": list(self.tags),
            "priority": self.priority.value,
            "status": self.status.value,
        }
