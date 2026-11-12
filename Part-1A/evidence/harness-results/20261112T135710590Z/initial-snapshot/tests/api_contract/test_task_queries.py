from __future__ import annotations

from fastapi.testclient import TestClient


def test_at006_tags_are_trimmed_lowercased_deduplicated_and_sorted(client: TestClient) -> None:
    created = client.post(
        "/tasks",
        json={"title": "Tagged", "tags": ["  Zebra ", "alpha", "ALPHA", " middle "]},
    )
    assert created.status_code == 201
    assert created.json()["tags"] == ["alpha", "middle", "zebra"]

    updated = client.patch("/tasks/1", json={"tags": ["BETA", " beta ", "Gamma"]})
    assert updated.status_code == 200
    assert updated.json()["tags"] == ["beta", "gamma"]


def test_at007_tag_filters_are_anded_normalized_deduplicated_and_can_match_nothing(client: TestClient) -> None:
    client.post("/tasks", json={"title": "One", "tags": ["home", "urgent"]})
    client.post("/tasks", json={"title": "Two", "tags": ["home"]})
    client.post("/tasks", json={"title": "Three", "tags": ["urgent"]})

    both = client.get("/tasks", params=[("tag", " HOME "), ("tag", "urgent"), ("tag", "home")])
    assert [task["title"] for task in both.json()["items"]] == ["One"]

    none = client.get("/tasks", params={"tag": "missing"})
    assert none.json() == {"items": [], "count": 0}


def test_at008_priority_values_default_and_invalid_inputs(client: TestClient) -> None:
    defaulted = client.post("/tasks", json={"title": "Default"})
    assert defaulted.status_code == 201
    assert defaulted.json()["priority"] == "Medium"

    for priority in ("Low", "Medium", "High"):
        response = client.post("/tasks", json={"title": priority, "priority": priority})
        assert response.status_code == 201
        assert response.json()["priority"] == priority

    invalid = client.post("/tasks", json={"title": "Invalid", "priority": "Urgent"})
    assert invalid.status_code == 422
    explicit_null = client.post("/tasks", json={"title": "Null", "priority": None})
    assert explicit_null.status_code == 422


def test_at009_priority_sort_is_stable_and_uses_task_id_for_ties(client: TestClient) -> None:
    for title, priority in (
        ("medium-first", "Medium"),
        ("low-first", "Low"),
        ("high-first", "High"),
        ("high-second", "High"),
        ("medium-second", "Medium"),
        ("low-second", "Low"),
    ):
        client.post("/tasks", json={"title": title, "priority": priority})

    sorted_tasks = client.get("/tasks", params={"sort": "priority"}).json()["items"]
    assert [task["title"] for task in sorted_tasks] == [
        "high-first",
        "high-second",
        "medium-first",
        "medium-second",
        "low-first",
        "low-second",
    ]
