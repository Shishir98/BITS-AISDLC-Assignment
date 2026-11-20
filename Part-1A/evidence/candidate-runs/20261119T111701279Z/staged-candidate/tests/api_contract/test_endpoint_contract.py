from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from smart_todo.app import create_app


def test_at019_success_and_applicable_error_statuses_for_every_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "store.json"), raise_server_exceptions=False)

    created = client.post("/tasks", json={"title": "Endpoint matrix"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    assert client.post("/tasks", json={"title": " "}).status_code == 422
    raw_json = {"data": "{not json}", "headers": {"content-type": "application/json"}}
    assert client.patch(f"/tasks/{task_id}", **raw_json).status_code == 400
    assert client.patch(f"/tasks/{task_id}/status", **raw_json).status_code == 400

    assert client.get("/tasks").status_code == 200
    assert client.get("/tasks", params={"sort": "unknown"}).status_code == 422
    assert client.get(f"/tasks/{task_id}").status_code == 200
    assert client.get("/tasks/999").status_code == 404
    assert client.get("/tasks/01").status_code == 422

    assert client.patch(f"/tasks/{task_id}", json={"title": "Changed"}).status_code == 200
    assert client.patch(f"/tasks/{task_id}", json={}).status_code == 422
    assert client.patch("/tasks/999", json={"title": "Missing"}).status_code == 404
    assert client.delete("/tasks/999").status_code == 404
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.delete(f"/tasks/{task_id}").status_code == 404

    status_task = client.post("/tasks", json={"title": "Status endpoint"}).json()
    status_id = status_task["id"]
    assert client.patch(f"/tasks/{status_id}/status", json={"status": "In Progress"}).status_code == 200
    assert client.patch(f"/tasks/{status_id}/status", json={"status": "Completed"}).status_code == 200
    assert client.patch(
        f"/tasks/{status_id}/status",
        json={"status": "In Progress"},
    ).status_code == 409
    assert client.patch(f"/tasks/{status_id}/status", json={"status": "Unknown"}).status_code == 422
    assert client.patch("/tasks/999/status", json={"status": "Pending"}).status_code == 404

    malformed_store = tmp_path / "malformed.json"
    malformed_store.write_text('{"next_id": false, "tasks": []}', encoding="utf-8")
    failing = TestClient(create_app(malformed_store), raise_server_exceptions=False)
    for method, url, kwargs in (
        ("get", "/tasks", {}),
        ("post", "/tasks", {"json": {"title": "Read failure"}}),
        ("get", "/tasks/1", {}),
        ("patch", "/tasks/1", {"json": {"title": "Read failure"}}),
        ("delete", "/tasks/1", {}),
        ("patch", "/tasks/1/status", {"json": {"status": "In Progress"}}),
    ):
        response = getattr(failing, method)(url, **kwargs)
        assert response.status_code == 500
