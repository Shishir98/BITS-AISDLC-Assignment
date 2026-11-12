from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_at010_all_task_status_values_are_returned(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "State"})
    assert created.json()["status"] == "Pending"

    in_progress = client.patch("/tasks/1/status", json={"status": "In Progress"})
    assert in_progress.status_code == 200
    assert in_progress.json()["status"] == "In Progress"

    completed = client.patch("/tasks/1/status", json={"status": "Completed"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "Completed"


def test_at011_only_forward_transitions_are_allowed_and_same_status_is_idempotent(
    client: TestClient, store_path: Path
) -> None:
    pending = client.post("/tasks", json={"title": "Forward"}).json()
    assert client.patch("/tasks/1/status", json={"status": "Pending"}).json() == pending
    in_progress = client.patch("/tasks/1/status", json={"status": "In Progress"})
    assert in_progress.status_code == 200
    assert json.loads(store_path.read_text(encoding="utf-8"))["tasks"][0]["status"] == "In Progress"
    assert client.patch("/tasks/1/status", json={"status": "In Progress"}).json() == in_progress.json()
    completed = client.patch("/tasks/1/status", json={"status": "Completed"})
    assert completed.status_code == 200
    assert json.loads(store_path.read_text(encoding="utf-8"))["tasks"][0]["status"] == "Completed"
    assert client.patch("/tasks/1/status", json={"status": "Completed"}).json() == completed.json()


def test_at012_prohibited_transitions_leave_persisted_status_unchanged(
    client: TestClient, store_path: Path
) -> None:
    transitions = (
        ("Pending", "Completed"),
        ("In Progress", "Pending"),
        ("Completed", "In Progress"),
        ("Completed", "Pending"),
    )
    for index, (current, target) in enumerate(transitions, start=1):
        created = client.post("/tasks", json={"title": f"Transition {index}"})
        assert created.status_code == 201
        if current in ("In Progress", "Completed"):
            assert client.patch(f"/tasks/{index}/status", json={"status": "In Progress"}).status_code == 200
        if current == "Completed":
            assert client.patch(f"/tasks/{index}/status", json={"status": "Completed"}).status_code == 200

        before = client.get(f"/tasks/{index}").json()
        stored_before = store_path.read_bytes()
        rejected = client.patch(f"/tasks/{index}/status", json={"status": target})
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "invalid_status_transition"
        assert client.get(f"/tasks/{index}").json() == before
        assert store_path.read_bytes() == stored_before
