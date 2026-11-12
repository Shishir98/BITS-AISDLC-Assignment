from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from smart_todo.app import create_app


def test_at002_ids_are_deterministic_and_never_reused_after_delete_or_restart(
    tmp_path: Path,
) -> None:
    first_store = tmp_path / "first.json"
    second_store = tmp_path / "second.json"
    first = TestClient(create_app(first_store))
    second = TestClient(create_app(second_store))

    first_ids = [
        first.post("/tasks", json={"title": "First"}).json()["id"],
        first.post("/tasks", json={"title": "Second"}).json()["id"],
    ]
    second_ids = [
        second.post("/tasks", json={"title": "First"}).json()["id"],
        second.post("/tasks", json={"title": "Second"}).json()["id"],
    ]
    assert first_ids == second_ids == [1, 2]

    assert first.delete("/tasks/1").status_code == 204
    restarted = TestClient(create_app(first_store))
    next_task = restarted.post("/tasks", json={"title": "Third"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == 3
