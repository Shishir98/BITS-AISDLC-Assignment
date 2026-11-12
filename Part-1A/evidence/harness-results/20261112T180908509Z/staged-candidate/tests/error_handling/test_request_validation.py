from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from smart_todo.app import create_app


def test_at016_title_and_description_boundary_values_and_invalid_values(
    client: TestClient, tmp_path: Path
) -> None:
    shortest = client.post("/tasks", json={"title": "x", "description": ""})
    assert shortest.status_code == 201
    null_description = client.post("/tasks", json={"title": "Null description", "description": None})
    assert null_description.status_code == 201
    assert null_description.json()["description"] is None
    longest = client.post("/tasks", json={"title": "t" * 200, "description": "d" * 2000})
    assert longest.status_code == 201
    assert len(longest.json()["title"]) == 200
    assert len(longest.json()["description"]) == 2000

    invalid_payloads = (
        {"title": ""},
        {"title": "   "},
        {"title": None},
        {"title": "t" * 201},
        {"title": "valid", "description": "d" * 2001},
        {"title": 7},
        {"title": "valid", "description": 7},
    )
    isolated = TestClient(create_app(tmp_path / "boundary-test.json"), raise_server_exceptions=False)
    for payload in invalid_payloads:
        response = isolated.post("/tasks", json=payload)
        assert response.status_code == 422


def test_at017_tag_count_length_and_normalization_boundaries(client: TestClient, tmp_path: Path) -> None:
    max_tags = [f"tag-{index}" for index in range(20)]
    accepted = client.post("/tasks", json={"title": "Max tags", "tags": max_tags})
    assert accepted.status_code == 201
    assert len(accepted.json()["tags"]) == 20
    assert client.post("/tasks", json={"title": "Max tag length", "tags": ["x" * 32]}).status_code == 201

    invalid_cases = (
        {"title": "Too many", "tags": [f"tag-{index}" for index in range(21)]},
        {"title": "Empty tag", "tags": ["   "]},
        {"title": "Long tag", "tags": ["x" * 33]},
        {"title": "Non-string tag", "tags": ["valid", 4]},
        {"title": "Not a list", "tags": "valid"},
    )
    isolated = TestClient(create_app(tmp_path / "tag-boundary-test.json"), raise_server_exceptions=False)
    for payload in invalid_cases:
        assert isolated.post("/tasks", json=payload).status_code == 422


def test_at018_malformed_json_ids_queries_and_enum_values_are_rejected(client: TestClient) -> None:
    malformed_json = client.post(
        "/tasks",
        data="{not json}",
        headers={"content-type": "application/json"},
    )
    assert malformed_json.status_code == 400
    assert malformed_json.json()["error"]["code"] == "invalid_json"

    for raw_id in ("0", "01", "-1", "1.0", "x"):
        response = client.get(f"/tasks/{raw_id}")
        assert response.status_code == 422

    invalid_query = client.get("/tasks", params={"sort": "title"})
    assert invalid_query.status_code == 422
    unknown_query = client.get("/tasks", params={"unexpected": "value"})
    assert unknown_query.status_code == 422
    invalid_status = client.patch("/tasks/1/status", json={"status": "Blocked"})
    assert invalid_status.status_code == 422
    extra_field = client.post("/tasks", json={"title": "No extras", "unexpected": True})
    assert extra_field.status_code == 422
    non_object = client.post("/tasks", json=["not", "an", "object"])
    assert non_object.status_code == 422


def test_at020_validation_errors_have_stable_sanitized_envelope(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "   ", "unexpected": "do not echo"})
    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["details"]
    assert all(set(detail) == {"field", "code", "message"} for detail in body["error"]["details"])
    assert body["error"]["details"] == sorted(body["error"]["details"], key=lambda item: item["field"])
    serialized = response.text.lower()
    assert "do not echo" not in serialized
    assert "traceback" not in serialized
    assert "c:\\users\\" not in serialized
