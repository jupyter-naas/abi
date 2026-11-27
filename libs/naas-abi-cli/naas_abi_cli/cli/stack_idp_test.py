"""`abi stack start` gives the built-in IdP its key and permissions (#1643)."""

from __future__ import annotations

import stat
from pathlib import Path

import click
import pytest
import yaml

from naas_abi_cli.cli.stack_idp import IDP_SERVICE_KEY, bootstrap_idp, idp_account

ACCOUNT = "module/demo/idp"
KEY = "abi_sk_" + "k" * 40


def _project(tmp_path: Path, *, idp: bool = True, env: str = "") -> Path:
    services: dict = {"abi": {"image": "abi"}}
    if idp:
        services["idp"] = {
            "environment": [
                "ABI_NATS_URL=nats://nats:4222",
                "ABI_DISCOVERY_PROJECT=demo",
            ]
        }
    (tmp_path / "docker-compose.yml").write_text(yaml.safe_dump({"services": services}))
    (tmp_path / ".env").write_text(env)
    return tmp_path


def _env(project: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in (project / ".env").read_text().splitlines()
        if "=" in line
    )


class FakeStack:
    """`docker compose`, with an `abi iam` that keeps accounts and manifests."""

    def __init__(
        self,
        *,
        accounts: tuple[str, ...] = (),
        manifests: list[tuple[str, str]] | None = None,
        submit_after: int = 0,
    ) -> None:
        self.accounts = set(accounts)
        self.manifests = list(manifests or [])
        # The idp submits its manifest after this many `module list` calls.
        self.submit_after = submit_after
        self.lists = 0
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], capture_output: bool = False):
        self.calls.append(args)
        out = ""
        if args[:3] == ["exec", "-T", "abi"]:
            out = self._iam(args[args.index("iam") + 1 :])
        return type("Result", (), {"stdout": out})()

    def _iam(self, args: list[str]) -> str:
        if args[:2] == ["service-account", "create"]:
            if args[2] in self.accounts:
                raise click.ClickException("exists")
            self.accounts.add(args[2])
            return f"sa_1\t{args[2]}\n{KEY}\n"
        if args[:2] == ["key", "create"]:
            if args[2] not in self.accounts:
                raise click.ClickException("no such account")
            return KEY + "\n"
        if args[:2] == ["module", "list"]:
            self.lists += 1
            if self.lists > self.submit_after and not self.manifests:
                self.manifests.append(("pending", "abc123def456"))
            return "".join(
                f"{status}\t{ACCOUNT}\t{sha}\tsubmitted now\n"
                for status, sha in self.manifests
            )
        if args[:2] == ["module", "approve"]:
            assert args[2] == ACCOUNT
            self.manifests = [
                ("approved" if s == "pending" else s, sha) for s, sha in self.manifests
            ]
            return "approved\n"
        raise AssertionError(args)

    def iam_calls(self) -> list[list[str]]:
        return [c[c.index("iam") + 1 :] for c in self.calls if "iam" in c]


def _run(project: Path, stack: FakeStack, **kwargs) -> None:
    bootstrap_idp(project, compose=stack, sleep=lambda s: None, **kwargs)


def test_the_idp_account_is_read_from_the_compose_file(tmp_path: Path) -> None:
    assert idp_account(_project(tmp_path)) == ACCOUNT
    assert idp_account(_project(tmp_path, idp=False)) is None
    (tmp_path / "docker-compose.yml").unlink()
    assert idp_account(tmp_path) is None


def test_a_fresh_stack_gets_a_key_and_approved_permissions(tmp_path: Path) -> None:
    project = _project(tmp_path, env="OTHER=kept\n")
    stack = FakeStack(submit_after=1)

    _run(project, stack)

    env = _env(project)
    assert env[IDP_SERVICE_KEY] == KEY and env["OTHER"] == "kept"
    assert stat.S_IMODE((project / ".env").stat().st_mode) == 0o600
    assert ["up", "-d", "idp"] in stack.calls
    assert stack.manifests == [("approved", "abc123def456")]
    # Only the idp's own account is approved.
    approvals = [c for c in stack.iam_calls() if c[:2] == ["module", "approve"]]
    assert approvals == [["module", "approve", ACCOUNT]]


def test_the_key_is_never_printed(tmp_path: Path, capsys) -> None:
    _run(_project(tmp_path), FakeStack())
    out = capsys.readouterr()
    assert KEY not in out.out and KEY not in out.err


def test_an_existing_account_gets_a_new_key(tmp_path: Path) -> None:
    project = _project(tmp_path)
    stack = FakeStack(accounts=(ACCOUNT,))

    _run(project, stack)

    assert _env(project)[IDP_SERVICE_KEY] == KEY
    assert ["key", "create", ACCOUNT, "--description", "idp (abi stack start)"] in (
        stack.iam_calls()
    )


def test_a_started_idp_is_left_alone(tmp_path: Path) -> None:
    project = _project(tmp_path, env=f"{IDP_SERVICE_KEY}={KEY}\n")
    stack = FakeStack(accounts=(ACCOUNT,), manifests=[("approved", "abc123def456")])

    _run(project, stack)

    assert stack.iam_calls() == [["module", "list"]]
    assert ["up", "-d", "idp"] not in stack.calls


def test_a_new_manifest_of_a_running_idp_waits_for_review(
    tmp_path: Path, capsys
) -> None:
    # Once a version is in force, a newer one is an operator's to review:
    # approving without review is the abi dev overlay's only (auto_approve).
    project = _project(tmp_path, env=f"{IDP_SERVICE_KEY}={KEY}\n")
    stack = FakeStack(
        accounts=(ACCOUNT,),
        manifests=[("approved", "aaa"), ("pending", "bbb")],
    )

    _run(project, stack)

    assert stack.manifests == [("approved", "aaa"), ("pending", "bbb")]
    assert not [c for c in stack.iam_calls() if c[:2] == ["module", "approve"]]
    out = capsys.readouterr().out
    assert "waits for review" in out
    assert f"abi iam module show {ACCOUNT}" in out


def test_a_rejected_manifest_is_reported_at_once(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path, env=f"{IDP_SERVICE_KEY}={KEY}\n")
    stack = FakeStack(accounts=(ACCOUNT,), manifests=[("rejected", "ccc")])

    _run(project, stack)

    assert stack.lists == 1  # no 2-min wait on an operator's decision
    assert not [c for c in stack.iam_calls() if c[:2] == ["module", "approve"]]
    out = capsys.readouterr().out
    assert "rejected" in out and "no permission manifest" not in out


def test_an_unwritable_env_does_not_stop_the_stack(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    from naas_abi_cli.cli import stack_idp

    def refuse(path, lines):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(stack_idp, "_write", refuse)
    project = _project(tmp_path)

    _run(project, FakeStack())

    out = capsys.readouterr()
    assert "identity provider is not started" in out.out
    assert "Permission denied" in out.out
    assert KEY not in out.out and KEY not in out.err


def test_no_manifest_in_time_says_what_to_check(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)
    stack = FakeStack(submit_after=10**6)

    _run(project, stack, timeout=15, poll=5)

    assert _env(project)[IDP_SERVICE_KEY] == KEY
    assert stack.lists == 4  # 0, 5, 10, 15 s
    assert "docker compose logs idp" in capsys.readouterr().out


def test_a_failing_iam_call_does_not_stop_the_stack(tmp_path: Path, capsys) -> None:
    project = _project(tmp_path)

    def broken(args: list[str], capture_output: bool = False):
        raise click.ClickException("docker compose exec failed with exit code 1.")

    bootstrap_idp(project, compose=broken, sleep=lambda s: None)

    out = capsys.readouterr().out
    assert "identity provider is not started" in out
    assert f"abi iam module approve {ACCOUNT}" in out
    assert IDP_SERVICE_KEY not in _env(project)


def test_a_project_without_idp_is_untouched(tmp_path: Path) -> None:
    project = _project(tmp_path, idp=False)
    stack = FakeStack()

    _run(project, stack)

    assert stack.calls == []


@pytest.mark.parametrize("value", ["", "not-a-key"])
def test_a_blank_or_foreign_key_is_replaced(tmp_path: Path, value: str) -> None:
    project = _project(tmp_path, env=f"{IDP_SERVICE_KEY}={value}\n")

    _run(project, FakeStack())

    assert _env(project)[IDP_SERVICE_KEY] == KEY
