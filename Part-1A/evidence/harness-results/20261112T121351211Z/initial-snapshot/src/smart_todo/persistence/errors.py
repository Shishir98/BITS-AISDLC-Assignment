class PersistenceError(RuntimeError):
    """Base class for storage failures."""


class MalformedStoredDataError(PersistenceError):
    """Raised when the persisted JSON document is invalid."""


class StoreWriteError(PersistenceError):
    """Raised when the local JSON store cannot be written."""
