# ruff: noqa: B008
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from ..api.schemas import (
    CreateTaskRequest,
    TaskCollection,
    UpdateTaskRequest,
    UpdateTaskStatusRequest,
)
from ..domain.errors import TaskValidationError
from ..domain.models import Task
from ..domain.service import _UNSET, TaskService

router = APIRouter()


def _get_service(request: Request) -> TaskService:
    return request.app.state.service


def _parse_task_id(raw: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise ValueError("Task id must be a positive decimal integer without leading zeros")
    return int(raw)


def _validated_task_id(raw: str) -> int:
    try:
        return _parse_task_id(raw)
    except ValueError as exc:
        raise TaskValidationError(str(exc)) from exc


@router.post("/tasks", status_code=201, response_model=Task)
def create_task(payload: CreateTaskRequest, request: Request, service: TaskService = Depends(_get_service)) -> JSONResponse:
    task = service.create_task(
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        priority=payload.priority,
    )
    return JSONResponse(
        status_code=201,
        content=task.model_dump(mode="json"),
        headers={"Location": f"/tasks/{task.id}"},
    )


@router.get("/tasks", response_model=TaskCollection)
def list_tasks(request: Request, service: TaskService = Depends(_get_service)) -> TaskCollection:
    known = {"tag", "sort"}
    extra = {key for key in request.query_params if key not in known}
    if extra:
        raise TaskValidationError(f"Unknown query parameter: {min(extra)}")

    tags = request.query_params.getlist("tag")
    sort = request.query_params.get("sort")
    if sort is not None and sort != "priority":
        raise TaskValidationError("sort must be either omitted or 'priority'")

    items = service.list_tasks(tags=tags or None, sort=sort)
    return TaskCollection(items=items, count=len(items))


@router.get("/tasks/{id}", response_model=Task)
def get_task(id: str, request: Request, service: TaskService = Depends(_get_service)) -> Task:
    task_id = _validated_task_id(id)
    return service.get_task(task_id)


@router.patch("/tasks/{id}", response_model=Task)
def update_task(id: str, payload: UpdateTaskRequest, request: Request, service: TaskService = Depends(_get_service)) -> Task:
    task_id = _validated_task_id(id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise TaskValidationError("At least one field must be provided")
    return service.update_task(
        task_id,
        title=changes.get("title", _UNSET),
        description=changes.get("description", _UNSET),
        tags=changes.get("tags", _UNSET),
        priority=changes.get("priority", _UNSET),
    )


@router.delete("/tasks/{id}")
def delete_task(id: str, request: Request, service: TaskService = Depends(_get_service)) -> Response:
    task_id = _validated_task_id(id)
    service.delete_task(task_id)
    return Response(status_code=204)


@router.patch("/tasks/{id}/status", response_model=Task)
def update_status(id: str, payload: UpdateTaskStatusRequest, request: Request, service: TaskService = Depends(_get_service)) -> Task:
    task_id = _validated_task_id(id)
    return service.update_status(task_id, payload.status)
