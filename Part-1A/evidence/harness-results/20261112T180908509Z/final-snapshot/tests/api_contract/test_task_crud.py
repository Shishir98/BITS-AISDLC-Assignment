from __future__ import annotations

from fastapi.testclient import TestClient


def test_at001_create_response_matches_task_contract(client: TestClient) -> None:
    response = client.post(
        "/tasks",
        json={
            "title": "  Prepare report  ",
            "description": "Quarterly results",
            "tags": ["work"],
            "priority": "High",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "title": "Prepare report",
        "description": "Quarterly results",
        "tags": ["work"],
        "priority": "High",
        "status": "Pending",
    }
    assert response.headers["location"] == "/tasks/1"


def test_at003_list_and_get_reflect_empty_existing_and_missing_tasks(client: TestClient) -> None:
    empty = client.get("/tasks")
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "count": 0}

    created = client.post("/tasks", json={"title": "Read spec"})
    task = created.json()
    listed = client.get("/tasks")
    assert listed.json() == {"items": [task], "count": 1}
    assert client.get("/tasks/1").json() == task

    missing = client.get("/tasks/99")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_at004_patch_changes_only_supplied_fields_and_rejects_empty_update(client: TestClient) -> None:
    created = client.post(
        "/tasks",
        json={"title": "Old title", "description": "Keep me", "tags": ["old"], "priority": "Low"},
    ).json()

    changed = client.patch("/tasks/1", json={"title": " New title ", "tags": ["new"]})
    assert changed.status_code == 200
    assert changed.json() == {
        **created,
        "title": "New title",
        "tags": ["new"],
    }

    cleared = client.patch("/tasks/1", json={"description": None})
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
    assert cleared.json()["priority"] == "Low"

    empty = client.patch("/tasks/1", json={})
    assert empty.status_code == 422
    assert client.get("/tasks/1").json() == cleared.json()


def test_at005_delete_has_no_response_body_and_missing_ids_are_404(client: TestClient) -> None:
    assert client.post("/tasks", json={"title": "Remove me"}).status_code == 201

    deleted = client.delete("/tasks/1")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/tasks/1").status_code == 404

    missing = client.delete("/tasks/1")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
