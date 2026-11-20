from __future__ import annotations

import socket
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from smart_todo.app import create_app

_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost", "testserver", "testclient", ""}
_ORIGINAL_CONNECT = socket.socket.connect
_ORIGINAL_CONNECT_EX = socket.socket.connect_ex
_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_SENDTO = socket.socket.sendto
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_ORIGINAL_URLOPEN = urllib.request.urlopen


def _extract_host(address: Any) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0]).strip().lower()
    if isinstance(address, (str, bytes)):
        return ""
    return str(address).strip().lower()


def _guard_external_host(address: Any) -> None:
    host = _extract_host(address)
    if host not in _ALLOWED_HOSTS:
        raise RuntimeError(f"External network access is disabled during automated tests (attempted host: {host})")


@pytest.fixture(autouse=True)
def _block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def guarded_connect(sock: socket.socket, address: Any) -> Any:
        _guard_external_host(address)
        return _ORIGINAL_CONNECT(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: Any) -> int:
        _guard_external_host(address)
        return _ORIGINAL_CONNECT_EX(sock, address)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        _guard_external_host(address)
        return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)

    def guarded_sendto(sock: socket.socket, data: Any, *args: Any) -> int:
        if args:
            _guard_external_host(args[-1])
        return _ORIGINAL_SENDTO(sock, data, *args)

    def guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        normalized = "" if host is None else str(host).strip().lower()
        if normalized not in _ALLOWED_HOSTS:
            raise RuntimeError(
                f"External DNS resolution is disabled during automated tests (attempted host: {normalized})"
            )
        return _ORIGINAL_GETADDRINFO(host, port, *args, **kwargs)

    def guarded_urlopen(url: Any, *args: Any, **kwargs: Any) -> Any:
        target = getattr(url, "full_url", url)
        parsed = urlparse(str(target))
        host = (parsed.hostname or "").strip().lower()
        if host not in _ALLOWED_HOSTS:
            raise RuntimeError(f"External HTTP access is disabled during automated tests (attempted host: {host})")
        return _ORIGINAL_URLOPEN(url, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(urllib.request, "urlopen", guarded_urlopen)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost,::1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("PIP_NO_INDEX", "1")
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    monkeypatch.setenv("UV_NO_CONFIG", "1")


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "tasks.json"


@pytest.fixture
def client(store_path: Path) -> TestClient:
    return TestClient(create_app(store_path))
