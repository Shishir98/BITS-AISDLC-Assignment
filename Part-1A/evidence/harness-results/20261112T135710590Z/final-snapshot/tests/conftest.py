from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_todo.app import create_app


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "tasks.json"


@pytest.fixture
def client(store_path: Path) -> TestClient:
    return TestClient(create_app(store_path))
