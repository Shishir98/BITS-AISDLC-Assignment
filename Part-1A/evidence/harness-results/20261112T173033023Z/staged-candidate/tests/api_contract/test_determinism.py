from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from smart_todo.app import create_app


def test_at021_identical_initial_state_and_request_sequence_produce_identical_results(
    tmp_path: Path,
) -> None:
    initial = (
        b'{"next_id":4,"tasks":[{"id":1,"title":"Seed","description":null,'
        b'"tags":["seed"],"priority":"Medium","status":"Pending"}]}'
    )
    stores = [tmp_path / "left.json", tmp_path / "right.json"]
    for store in stores:
        store.write_bytes(initial)

    results: list[list[tuple[int, object, str | None]]] = []
    for store in stores:
        client = TestClient(create_app(store))
        sequence = [
            client.get("/tasks"),
            client.post("/tasks", json={"title": "New", "tags": ["B", "a"]}),
            client.patch("/tasks/4", json={"description": "updated"}),
            client.patch("/tasks/4/status", json={"status": "In Progress"}),
            client.get("/tasks", params={"sort": "priority"}),
        ]
        results.append(
            [
                (response.status_code, response.json(), response.headers.get("location"))
                for response in sequence
            ]
        )
    assert results[0] == results[1]
