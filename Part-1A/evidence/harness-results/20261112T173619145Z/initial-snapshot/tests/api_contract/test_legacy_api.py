from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from smart_todo.app import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "tasks.json"))


def test_create_and_list_tasks(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/tasks", json={"title": "Pay bill", "tags": ["Home", "Urgent", "home"]})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == "Pay bill"
    assert body["description"] is None
    assert body["tags"] == ["home", "urgent"]
    assert body["priority"] == "Medium"
    assert body["status"] == "Pending"
    assert response.headers["Location"] == "/tasks/1"

    list_response = client.get("/tasks")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    task = client.get("/tasks/1")
    assert task.status_code == 200
    assert task.json()["title"] == "Pay bill"


def test_tag_filter_and_priority_sort(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/tasks", json={"title": "A", "priority": "Low", "tags": ["alpha"]})
    client.post("/tasks", json={"title": "B", "priority": "High", "tags": ["beta", "alpha"]})
    client.post("/tasks", json={"title": "C", "priority": "Medium", "tags": ["alpha"]})

    filtered = client.get("/tasks", params={"tag": ["alpha", "beta"]})
    assert filtered.status_code == 200
    assert [item["title"] for item in filtered.json()["items"]] == ["B"]

    sorted_response = client.get("/tasks", params={"sort": "priority"})
    assert [item["title"] for item in sorted_response.json()["items"]] == ["B", "C", "A"]


def test_status_transitions_and_invalid_update(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"title": "Study"})
    task_id = task.json()["id"]

    current = client.patch(f"/tasks/{task_id}/status", json={"status": "In Progress"})
    assert current.status_code == 200
    assert current.json()["status"] == "In Progress"

    done = client.patch(f"/tasks/{task_id}/status", json={"status": "Completed"})
    assert done.status_code == 200
    assert done.json()["status"] == "Completed"

    rejected = client.patch(f"/tasks/{task_id}/status", json={"status": "In Progress"})
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "invalid_status_transition"

    update = client.patch(f"/tasks/{task_id}", json={})
    assert update.status_code == 422


def test_store_malformed_access_returns_500(tmp_path: Path) -> None:
    store = tmp_path / "tasks.json"
    store.write_text('{"next_id": 2, "tasks": [1]}', encoding="utf-8")
    client = _client(tmp_path)
    response = client.get("/tasks")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "malformed_stored_data"
    assert store.read_text(encoding="utf-8") == '{"next_id": 2, "tasks": [1]}'


def test_invalid_json_and_bad_id(tmp_path: Path) -> None:
    client = _client(tmp_path)

    bad_json = client.post("/tasks", data="{not valid json}", headers={"content-type": "application/json"})
    assert bad_json.status_code == 400
    assert bad_json.json()["error"]["code"] == "invalid_json"

    bad_id = client.get("/tasks/01")
    assert bad_id.status_code == 422
    assert bad_id.json()["error"]["code"] == "validation_error"
