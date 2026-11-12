from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..domain.errors import (
    InvalidStatusTransitionError,
    TaskNotFoundError,
    TaskValidationError,
)
from ..persistence.errors import MalformedStoredDataError, PersistenceError


def build_error_response(code: str, message: str, status_code: int, details: list[dict[str, str]] | None = None) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


def format_validation_details(exc: RequestValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field = "body"
        if loc and loc[0] in {"query", "path", "header", "cookie"}:
            field = ".".join(str(part) for part in loc if part not in {"body"})
        elif loc:
            field = ".".join(str(part) for part in loc if part != "body")
        if not field:
            field = "body"
        code = "validation_error"
        message = str(error.get("msg", "Invalid request"))
        details.append({"field": field, "code": code, "message": message})
    details.sort(key=lambda item: (item["field"], item["code"], item["message"]))
    return details


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    if any((err.get("type") == "json_invalid" or "JSON" in str(err.get("msg", ""))) for err in exc.errors()):
        return build_error_response("invalid_json", "Request body is not valid JSON", 400)
    return build_error_response("validation_error", "Request validation failed", 422, format_validation_details(exc))


async def not_found_exception_handler(request: Request, exc: TaskNotFoundError) -> JSONResponse:
    return build_error_response("not_found", "Task not found", 404)


async def invalid_transition_exception_handler(request: Request, exc: InvalidStatusTransitionError) -> JSONResponse:
    return build_error_response("invalid_status_transition", "Status transition is not allowed", 409)


async def task_validation_exception_handler(request: Request, exc: TaskValidationError) -> JSONResponse:
    return build_error_response("validation_error", "Request validation failed", 422, [{"field": "body", "code": "validation_error", "message": str(exc)}])


async def malformed_store_exception_handler(request: Request, exc: MalformedStoredDataError) -> JSONResponse:
    return build_error_response("malformed_stored_data", "Stored data is malformed", 500)


async def persistence_exception_handler(request: Request, exc: PersistenceError) -> JSONResponse:
    return build_error_response("persistence_error", "Failed to persist task data", 500)
