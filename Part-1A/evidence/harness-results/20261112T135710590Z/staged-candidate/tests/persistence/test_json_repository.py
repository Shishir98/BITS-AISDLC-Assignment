from __future__ import annotations

import json
from pathlib import Path
from typing import Self

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


def test_at014_failed_atomic_write_preserves_file_and_in_memory_state(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path), raise_server_exceptions=False)
    original = client.post("/tasks", json={"title": "Original"})
    assert original.status_code == 201
    old_bytes = store_path.read_bytes()

    real_named_temporary_file = __import__(
        "smart_todo.persistence.json_repository", fromlist=["tempfile"]
    ).tempfile.NamedTemporaryFile

    class FailedWriter:
        def __init__(self, **kwargs: object) -> None:
            self.handle = real_named_temporary_file(**kwargs)

        def __enter__(self) -> Self:
            self.handle.__enter__()
            return self

        def __getattr__(self, name: str) -> object:
            return getattr(self.handle, name)

        def write(self, value: str) -> int:
            raise OSError("synthetic write failure")

        def __exit__(self, *args: object) -> object:
            return self.handle.__exit__(*args)

    monkeypatch.setattr(
        "smart_todo.persistence.json_repository.tempfile.NamedTemporaryFile",
        FailedWriter,
    )
    failed_write = client.post("/tasks", json={"title": "Write must not commit"})
    assert failed_write.status_code == 500
    assert store_path.read_bytes() == old_bytes
    assert client.get("/tasks").json()["items"] == [original.json()]

    monkeypatch.undo()

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("synthetic replacement failure")

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", fail_replace)
    failed = client.post("/tasks", json={"title": "Must not commit"})
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "persistence_error"
    assert store_path.read_bytes() == old_bytes
    assert client.get("/tasks").json()["items"] == [original.json()]
    monkeypatch.undo()
    after_failure = client.post("/tasks", json={"title": "Next valid task"})
    assert after_failure.status_code == 201
    assert after_failure.json()["id"] == 2


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
