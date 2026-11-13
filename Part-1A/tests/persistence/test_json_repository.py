from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient

from smart_todo.app import create_app


def test_at013_restart_restores_tasks_and_continues_monotonic_ids(store_path: Path) -> None:
    first = TestClient(create_app(store_path))
    one = first.post("/tasks", json={"title": "One"}).json()
    two = first.post("/tasks", json={"title": "Two"}).json()
    assert [one["id"], two["id"]] == [1, 2]

    restarted = TestClient(create_app(store_path))
    assert restarted.get("/tasks").json()["items"] == [one, two]
    next_task = restarted.post("/tasks", json={"title": "Three"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == 3


def test_at014_successful_write_verifies_backup_and_complete_candidate(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path))
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    repository = client.app.state.service._repository
    real_replace = os.replace
    candidate_bytes: list[bytes] = []

    def inspect_then_replace(source: str | Path, destination: str | Path) -> None:
        candidate_path = Path(source)
        backups = list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak"))
        assert len(backups) == 1
        assert backups[0].parent == store_path.parent
        assert backups[0].read_bytes() == previous_bytes
        candidate_bytes.append(candidate_path.read_bytes())
        assert candidate_path.parent == store_path.parent
        real_replace(source, destination)

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", inspect_then_replace)
    created = client.post("/tasks", json={"title": "Next"})

    assert created.status_code == 201
    expected = {
        "next_id": 3,
        "tasks": [
            original,
            {
                "id": 2,
                "title": "Next",
                "description": None,
                "tags": [],
                "priority": "Medium",
                "status": "Pending",
            },
        ],
    }
    assert json.loads(candidate_bytes[0].decode("utf-8")) == expected
    assert store_path.read_bytes() == candidate_bytes[0]
    assert list(store_path.parent.glob(f".{store_path.name}.*.tmp")) == []
    assert list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak")) == []
    assert client.get("/tasks").json()["items"] == expected["tasks"]
    assert repository._requires_recovery is False


def test_at014_candidate_serialization_failure_does_not_touch_store_or_memory(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    repository = client.app.state.service._repository
    temporary_calls = 0

    def fail_serialization(tasks: object, next_id: int) -> bytes:
        raise ValueError("synthetic serialization failure")

    def track_temporary_file(*args: Any, **kwargs: Any) -> Any:
        nonlocal temporary_calls
        temporary_calls += 1
        raise AssertionError("serialization must finish before file creation")

    monkeypatch.setattr(repository, "_serialize_candidate", fail_serialization)
    monkeypatch.setattr(
        "smart_todo.persistence.json_repository.tempfile.NamedTemporaryFile",
        track_temporary_file,
    )
    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert temporary_calls == 0
    assert store_path.read_bytes() == previous_bytes
    assert client.get("/tasks").json()["items"] == [original]


def test_at014_candidate_temporary_write_failure_recovers_and_allows_next_write(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    _fail_temporary_write(monkeypatch, ".tmp")

    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert store_path.read_bytes() == previous_bytes
    assert client.get("/tasks").json()["items"] == [original]
    assert list(store_path.parent.glob(f".{store_path.name}.*.tmp")) == []
    monkeypatch.undo()
    next_task = client.post("/tasks", json={"title": "Next"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == 2


def test_at014_backup_write_failure_leaves_verified_original_and_memory_unchanged(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    _fail_temporary_write(monkeypatch, ".bak")

    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert store_path.read_bytes() == previous_bytes
    assert client.get("/tasks").json()["items"] == [original]
    assert list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak")) == []
    monkeypatch.undo()
    next_task = client.post("/tasks", json={"title": "Next"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == 2


def test_at014_replacement_failure_restores_exact_bytes_and_allows_next_write(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    real_replace = os.replace
    attempts = 0

    def fail_before_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("synthetic replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", fail_before_replace)
    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert store_path.read_bytes() == previous_bytes
    assert client.get("/tasks").json()["items"] == [original]
    assert list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak")) == []
    monkeypatch.undo()
    next_task = client.post("/tasks", json={"title": "Next"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == 2


def test_at014_replacement_failure_after_install_restores_from_verified_backup(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    real_replace = os.replace
    attempts = 0

    def install_then_fail_once(source: str | Path, destination: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        real_replace(source, destination)
        if attempts == 1:
            raise OSError("synthetic failure after replacement")

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", install_then_fail_once)
    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert store_path.read_bytes() == previous_bytes
    assert client.get("/tasks").json()["items"] == [original]
    assert attempts == 2
    assert list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak")) == []
    monkeypatch.undo()
    next_task = client.post("/tasks", json={"title": "Next"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == 2


def test_at014_failed_creation_restores_original_absence(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    assert client.get("/tasks").json()["items"] == []
    assert not store_path.exists()
    real_replace = os.replace
    real_unlink = Path.unlink

    def install_then_fail(source: str | Path, destination: str | Path) -> None:
        real_replace(source, destination)
        raise OSError("synthetic failure after new store installation")

    def unlink_then_fail(path: Path, *, missing_ok: bool = False) -> None:
        real_unlink(path, missing_ok=missing_ok)
        if path == store_path:
            raise OSError("synthetic error after removing partially installed store")

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", install_then_fail)
    monkeypatch.setattr(Path, "unlink", unlink_then_fail)
    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert not store_path.exists()
    assert client.get("/tasks").json()["items"] == []
    assert list(store_path.parent.glob(f".{store_path.name}.*.tmp")) == []
    monkeypatch.undo()
    created = client.post("/tasks", json={"title": "First"})
    assert created.status_code == 201
    assert created.json()["id"] == 1


def test_at014_recovery_failure_preserves_backup_and_fails_closed(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"}).json()
    previous_bytes = store_path.read_bytes()
    real_replace = os.replace
    attempts = 0

    def fail_restore(source: str | Path, destination: str | Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            real_replace(source, destination)
            raise OSError("synthetic failure after replacement")
        raise OSError("synthetic restoration failure")

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", fail_restore)
    failed = client.post("/tasks", json={"title": "Must not commit"})

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert "traceback" not in failed.text.lower()
    assert str(store_path).lower() not in failed.text.lower()
    backups = list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == previous_bytes
    assert store_path.read_bytes() != previous_bytes
    assert client.get("/tasks").json()["items"] == [original]
    rejected = client.post("/tasks", json={"title": "Unsafe subsequent mutation"})
    assert rejected.status_code == 500
    assert rejected.json()["error"]["code"] == "persistence_error"
    assert store_path.read_bytes() != previous_bytes
    assert backups[0].read_bytes() == previous_bytes


def test_at014_cleanup_failure_does_not_undo_verified_commit(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path))
    client.post("/tasks", json={"title": "Original"})
    previous_unlink = Path.unlink

    def fail_backup_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        if path.name.endswith(".bak"):
            raise OSError("synthetic cleanup failure")
        previous_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_backup_cleanup)
    created = client.post("/tasks", json={"title": "Committed"})

    assert created.status_code == 201
    assert client.get("/tasks").json()["items"][-1]["title"] == "Committed"
    assert json.loads(store_path.read_text(encoding="utf-8"))["next_id"] == 3
    backups = list(store_path.parent.glob(f".{store_path.name}.recovery.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() != store_path.read_bytes()


def test_at015_table_driven_malformed_store_fixtures_fail_closed_without_rewriting(
    tmp_path: Path,
) -> None:
    valid_task = {
        "id": 1,
        "title": "Stored",
        "description": None,
        "tags": [],
        "priority": "Medium",
        "status": "Pending",
    }
    malformed_documents = (
        "",
        "{not json}",
        "[]",
        '{"next_id": true, "tasks": []}',
        '{"next_id": 0, "tasks": []}',
        '{"next_id": 3, "tasks": [1]}',
        '{"next_id": 3, "tasks": [{"id": 1}]}',
        json.dumps({"next_id": 3, "tasks": [valid_task, valid_task]}),
        '{"next_id": 3, "tasks": [], "extra": 1}',
        '{"next_id": 3, "tasks": [], "tasks": []}',
    )

    for index, document in enumerate(malformed_documents):
        path = tmp_path / f"malformed-{index}.json"
        original = document.encode("utf-8")
        path.write_bytes(original)
        client = TestClient(create_app(path), raise_server_exceptions=False)
        response = client.get("/tasks")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "malformed_stored_data"
        assert "traceback" not in response.text.lower()
        assert "c:\\users\\" not in response.text.lower()
        repeated = client.get("/tasks")
        assert repeated.status_code == 500
        assert repeated.json() == response.json()
        assert path.read_bytes() == original


def _fail_temporary_write(monkeypatch: pytest.MonkeyPatch, target_suffix: str) -> None:
    from smart_todo.persistence import json_repository

    real_named_temporary_file = json_repository.tempfile.NamedTemporaryFile

    class FailedWriter:
        def __init__(self, handle: Any) -> None:
            self.handle = handle

        def __enter__(self) -> Self:
            self.handle.__enter__()
            return self

        def __getattr__(self, name: str) -> Any:
            return getattr(self.handle, name)

        def write(self, value: bytes) -> int:
            self.handle.write(value[: max(1, len(value) // 2)])
            raise OSError("synthetic temporary write failure")

        def __exit__(self, *args: object) -> object:
            return self.handle.__exit__(*args)

    def named_temporary_file(*args: Any, **kwargs: Any) -> Any:
        handle = real_named_temporary_file(*args, **kwargs)
        if kwargs.get("suffix") == target_suffix:
            return FailedWriter(handle)
        return handle

    monkeypatch.setattr(
        "smart_todo.persistence.json_repository.tempfile.NamedTemporaryFile",
        named_temporary_file,
    )
