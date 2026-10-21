"""What the broker user ``module`` may serve: its own subjects and no more.

The tools a module serves are on ``abi.mod.<project>.<instance>.tool.<name>.invoke``.
``MODULE_PERMISSIONS`` is a deny list, so serving them needs no entry; what it must
keep denying is everything a module could use to answer for the engine: the engine's
services (the tool catalog among them), discovery and its replies.
"""

from __future__ import annotations

import pytest
from naas_abi_core.engine.nats_permissions import (
    MODULE_PERMISSIONS,
    authorization_config,
)
from naas_abi_sdk.tools import tool_subject


def matches(pattern: str, subject: str) -> bool:
    """NATS wildcard matching: ``*`` is one token, a trailing ``>`` is one or more."""
    wanted, actual = pattern.split("."), subject.split(".")
    for index, token in enumerate(wanted):
        if token == ">":
            return len(actual) > index
        if index >= len(actual) or token not in ("*", actual[index]):
            return False
    return len(wanted) == len(actual)


def denied(direction: str, subject: str) -> bool:
    return any(matches(p, subject) for p in MODULE_PERMISSIONS[direction]["deny"])


def test_a_module_may_serve_and_call_a_tool_subject():
    subject = tool_subject("acme", "instance-1", "lookup")
    assert subject == "abi.mod.acme.instance-1.tool.lookup.invoke"
    assert not denied("subscribe", subject)
    assert not denied("publish", subject)


def test_a_module_may_call_the_engines_tool_operations_but_not_serve_them():
    """Running an engine tool is a call to ``abi.svc.tool_registry.v1.invoke_tool``: a
    module publishes there (the engine checks its token), and could not answer it."""
    for operation in ("search_tools", "invoke_tool"):
        subject = f"abi.svc.tool_registry.v1.{operation}"
        assert not denied("publish", subject)
        assert denied("subscribe", subject)


@pytest.mark.parametrize(
    "subject",
    [
        "abi.svc.tool_registry.v1.list_tools",
        "abi.svc.tool_registry.v1.get_tool",
        "abi.svc.tool_registry.v1.search_tools",
        "abi.svc.tool_registry.v1.invoke_tool",
        "abi.discovery.acme.v1.authorize_tool",
        "abi.discovery.acme.v1.register",
        "abi.rpc.overflow.open",
        "_INBOX.engine-replies",
    ],
)
def test_a_module_cannot_serve_the_engines_subjects(subject):
    assert denied("subscribe", subject)


def test_the_brokers_module_user_carries_exactly_these_permissions():
    config = authorization_config({"abi": "a", "module": "m"})
    for pattern in MODULE_PERMISSIONS["subscribe"]["deny"]:
        assert f'"{pattern}"' in config
