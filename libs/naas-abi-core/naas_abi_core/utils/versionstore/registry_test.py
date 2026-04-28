"""Tests for StoreRegistry."""

from __future__ import annotations

from pathlib import Path

import pytest

from .registry import StoreRegistry


def test_get_creates_store(tmp_path: Path):
    reg = StoreRegistry(tmp_path)
    s = reg.get("users")
    s.put("alice", b"hi")
    s.close()
    assert reg.exists("users")


def test_namespaces_are_isolated(tmp_path: Path):
    reg = StoreRegistry(tmp_path)
    users = reg.get("users")
    configs = reg.get("configs")
    users.put("alice", b"U")
    configs.put("alice", b"C")
    assert users.get("alice") == b"U"
    assert configs.get("alice") == b"C"
    users.close()
    configs.close()


def test_list(tmp_path: Path):
    reg = StoreRegistry(tmp_path)
    reg.get("a").close()
    reg.get("b").close()
    assert set(reg.list()) == {"a", "b"}


def test_drop(tmp_path: Path):
    reg = StoreRegistry(tmp_path)
    s = reg.get("tmp")
    s.put("x", b"y")
    s.close()
    assert reg.exists("tmp")
    reg.drop("tmp")
    assert not reg.exists("tmp")


def test_invalid_name(tmp_path: Path):
    reg = StoreRegistry(tmp_path)
    for bad in ["", "../x", "a/b", "."]:
        with pytest.raises(ValueError):
            reg.get(bad)
