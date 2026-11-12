class TaskNotFoundError(KeyError):
    """Raised when a task identifier does not exist."""


class InvalidStatusTransitionError(ValueError):
    """Raised when a status transition is prohibited by the task lifecycle."""


class TaskValidationError(ValueError):
    """Raised when a task update or creation payload violates business rules."""
