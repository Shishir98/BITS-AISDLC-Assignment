from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.models import Priority, Task, TaskStatus


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM

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
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in value:
            if not isinstance(tag, str):
                raise TypeError("tag values must be strings")
            cleaned = tag.strip().lower()
            if not 1 <= len(cleaned) <= 32:
                raise ValueError("tag values must be 1-32 characters after normalization")
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        return sorted(normalized)

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, value: Priority | str | None) -> Priority:
        if value is None:
            raise ValueError("priority must be Low, Medium, or High")
        if isinstance(value, Priority):
            return value
        if not isinstance(value, str):
            raise ValueError("priority must be Low, Medium, or High")
        try:
            return Priority(value)
        except ValueError as exc:
            raise ValueError("priority must be Low, Medium, or High") from exc


class UpdateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    priority: Priority | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
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
    def validate_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise TypeError("tags must be a list")
        if len(value) > 20:
            raise ValueError("tags must contain at most 20 entries")
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in value:
            if not isinstance(tag, str):
                raise TypeError("tag values must be strings")
            cleaned = tag.strip().lower()
            if not 1 <= len(cleaned) <= 32:
                raise ValueError("tag values must be 1-32 characters after normalization")
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        return sorted(normalized)

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, value: Priority | str | None) -> Priority:
        if value is None:
            raise ValueError("priority must be Low, Medium, or High")
        if isinstance(value, Priority):
            return value
        if not isinstance(value, str):
            raise ValueError("priority must be Low, Medium, or High")
        try:
            return Priority(value)
        except ValueError as exc:
            raise ValueError("priority must be Low, Medium, or High") from exc



class UpdateTaskStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TaskStatus


class TaskCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[Task]
    count: int


class TaskListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: list[str] | None = Field(default=None)
    sort: Annotated[Literal["priority"], Field(...)] | None = None
