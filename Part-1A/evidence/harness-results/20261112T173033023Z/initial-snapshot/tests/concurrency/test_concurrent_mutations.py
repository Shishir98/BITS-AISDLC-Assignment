from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_todo.app import create_app


def test_at029_concurrent_creates_have_unique_monotonic_ids_and_survive_restart(
    store_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(store_path))
    count = 32

    def create(index: int) -> tuple[int, int]:
        response = client.post("/tasks", json={"title": f"Concurrent {index}"})
        return response.status_code, response.json()["id"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(create, range(count)))

    assert all(status == 201 for status, _ in results)
    identifiers = [task_id for _, task_id in results]
    assert sorted(identifiers) == list(range(1, count + 1))

    listed = client.get("/tasks")
    assert listed.status_code == 200
    assert listed.json()["count"] == count
    assert [task["id"] for task in listed.json()["items"]] == list(range(1, count + 1))

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("synthetic persistence failure")

    monkeypatch.setattr("smart_todo.persistence.json_repository.os.replace", fail_replace)
    failed = client.post("/tasks", json={"title": "Must not commit"})
    assert failed.status_code == 500
    assert client.get("/tasks").json()["count"] == count
    monkeypatch.undo()

    committed = client.post("/tasks", json={"title": "After failed write"})
    assert committed.status_code == 201
    assert committed.json()["id"] == count + 1

    update_url = f"/tasks/{count + 1}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        updates = list(
            executor.map(
                lambda payload: client.patch(update_url, json=payload),
                (
                    {"title": "Concurrent title"},
                    {"description": "Concurrent description"},
                ),
            )
        )
    assert [response.status_code for response in updates] == [200, 200]
    updated = client.get(update_url)
    assert updated.status_code == 200
    assert updated.json()["title"] == "Concurrent title"
    assert updated.json()["description"] == "Concurrent description"
    stored_task = next(
        task
        for task in json.loads(store_path.read_text(encoding="utf-8"))["tasks"]
        if task["id"] == count + 1
    )
    assert stored_task == updated.json()

    restarted = TestClient(create_app(store_path))
    assert restarted.get(update_url).json() == updated.json()
    next_task = restarted.post("/tasks", json={"title": "After restart"})
    assert next_task.status_code == 201
    assert next_task.json()["id"] == count + 2
