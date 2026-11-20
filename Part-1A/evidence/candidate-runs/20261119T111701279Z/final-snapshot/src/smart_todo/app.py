from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .api.errors import (
    invalid_transition_exception_handler,
    malformed_store_exception_handler,
    not_found_exception_handler,
    persistence_exception_handler,
    request_validation_exception_handler,
    task_validation_exception_handler,
)
from .api.routes import router
from .domain.errors import (
    InvalidStatusTransitionError,
    TaskNotFoundError,
    TaskValidationError,
)
from .domain.service import TaskService
from .persistence.errors import MalformedStoredDataError, PersistenceError
from .persistence.json_repository import JsonTaskRepository


def _resolve_store_path(store_path: Path | None = None) -> Path:
    if store_path is not None:
        path = Path(store_path)
    elif os.getenv("SMART_TODO_STORE_PATH"):
        path = Path(os.environ["SMART_TODO_STORE_PATH"])
    else:
        path = Path("data/tasks.json")

    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def create_app(store_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Smart Todo API")
    resolved = _resolve_store_path(store_path)
    app.state.service = TaskService(JsonTaskRepository(resolved))

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(TaskNotFoundError, not_found_exception_handler)
    app.add_exception_handler(InvalidStatusTransitionError, invalid_transition_exception_handler)
    app.add_exception_handler(TaskValidationError, task_validation_exception_handler)
    app.add_exception_handler(MalformedStoredDataError, malformed_store_exception_handler)
    app.add_exception_handler(PersistenceError, persistence_exception_handler)

    app.include_router(router)
    return app


app = create_app()
