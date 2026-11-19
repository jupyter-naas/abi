"""What the repository's workflows and locks keep: actions pinned by commit,
tooling installed with hashes, the release PAT apart from PyPI publishing,
deploys after a successful build only, a release-age cooldown on the locks,
and a reason for every advisory the check lets through."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((REPO / ".github/workflows").glob("*.yml"))
PACKAGES = [
    "naas-abi-proto",
    "naas-abi-sdk",
    "naas-abi-idp",
    "naas-abi-core",
    "naas-abi-marketplace",
    "naas-abi",
    "naas-abi-cli",
]


def _load(path: Path) -> dict:
    # PyYAML reads the `on:` key as True.
    return yaml.safe_load(path.read_text())


def _steps(workflow: dict):
    for name, job in workflow["jobs"].items():
        for step in job.get("steps") or []:
            yield name, job, step


@pytest.mark.parametrize("path", WORKFLOWS, ids=[p.name for p in WORKFLOWS])
def test_workflow_keeps_every_action_pinned_by_commit(path: Path) -> None:
    for _, _, step in _steps(_load(path)):
        if "uses" in step and not step["uses"].startswith("./"):
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", step["uses"]), step[
                "uses"
            ]


@pytest.mark.parametrize("path", WORKFLOWS, ids=[p.name for p in WORKFLOWS])
def test_workflow_keeps_pip_installs_hashed(path: Path) -> None:
    for _, _, step in _steps(_load(path)):
        for line in str(step.get("run") or "").splitlines():
            if re.search(r"\bpip3? install\b", line):
                assert "--require-hashes -r .github/requirements/" in line, line


@pytest.mark.parametrize("name", ["deploy.txt", "release.txt"])
def test_ci_requirements_keep_every_package_hashed(name: str) -> None:
    text = re.sub(r"\\\n\s*", " ", (REPO / ".github/requirements" / name).read_text())
    pins = [
        line for line in text.splitlines() if "==" in line and not line.startswith("#")
    ]
    assert pins
    assert all("--hash=sha256:" in line for line in pins)


def test_release_keeps_its_token_apart_from_publishing() -> None:
    release = _load(REPO / ".github/workflows/release.yml")
    assert release["permissions"] == {"contents": "read"}
    jobs = release["jobs"]
    # The job that holds the PAT cannot mint PyPI tokens...
    assert "id-token" not in jobs["release"]["permissions"]
    checkout = jobs["release"]["steps"][0]
    assert checkout["with"]["persist-credentials"] is False
    holders = [
        step["name"]
        for _, _, step in _steps(release)
        if "M_ACCESS_TOKEN" in yaml.safe_dump(step)
    ]
    assert holders == ["Release | Version, build and GitHub release of each package"]
    # ...and the one that can holds nothing else.
    publish = jobs["publish"]
    assert publish["permissions"] == {"id-token": "write"}
    assert publish["needs"] == "release"
    assert "secrets." not in yaml.safe_dump(publish)
    uploads = [
        step for step in publish["steps"] if "pypi-publish" in step.get("uses", "")
    ]
    assert [step["with"]["packages-dir"] for step in uploads] == [
        f"libs/{p}/dist" for p in PACKAGES
    ]


def test_release_builds_keep_to_the_pinned_tooling() -> None:
    for package in PACKAGES:
        pyproject = tomllib.loads(
            (REPO / "libs" / package / "pyproject.toml").read_text()
        )
        command = pyproject["tool"]["semantic_release"]["build_command"]
        assert "pip install" not in command, package


def test_deploy_keeps_to_successful_builds_and_the_job_token() -> None:
    deploy = _load(REPO / ".github/workflows/deploy_api.yml")
    assert deploy["permissions"] == {"contents": "read", "packages": "read"}
    assert (
        "github.event.workflow_run.conclusion == 'success'"
        in deploy["jobs"]["gate"]["if"]
    )
    for path in (
        ".github/workflows/deploy_api.yml",
        ".github/workflows/build_abi_container.yml",
    ):
        for _, _, step in _steps(_load(REPO / path)):
            if "docker/login-action" in step.get("uses", ""):
                assert step["with"]["password"] == "${{ secrets.GITHUB_TOKEN }}"


@pytest.mark.parametrize(
    "project",
    [REPO, REPO / "libs/naas-abi/naas_abi/apps/nexus/apps/api"],
    ids=["root", "nexus-api"],
)
def test_lock_keeps_a_release_age_cooldown(project: Path) -> None:
    pyproject = tomllib.loads((project / "pyproject.toml").read_text())
    assert pyproject["tool"]["uv"]["exclude-newer"] == "7 days"
    lock = tomllib.loads((project / "uv.lock").read_text())
    assert lock["options"]["exclude-newer-span"] == "P7D"
    # Never published, so under the prefix ABI holds on PyPI.
    assert pyproject["project"]["name"].startswith("naas-abi-")


def test_advisory_allowlist_keeps_a_reason_per_entry() -> None:
    lines = (REPO / ".github/advisories-allowlist.txt").read_text().splitlines()
    entries = [line for line in lines if line.strip() and not line.startswith("#")]
    assert entries
    for line in entries:
        assert re.fullmatch(
            r"(GHSA-[\w-]+|PYSEC-\d+-\d+|CVE-\d+-\d+) (ignore|until-fixed)  # \S+ \S+: .{10,}",
            line,
        ), line
