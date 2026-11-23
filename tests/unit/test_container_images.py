"""What the container image workflows keep: images for naas-abi releases only,
nexus-web built natively for both platforms then merged, a timeout on every
job, and one rule, run right before tagging, for when :latest moves."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github/workflows"
NEXUS_WEB = WORKFLOWS / "build_nexus_web_container.yml"
ABI = WORKFLOWS / "build_abi_container.yml"
RULE = REPO / ".github/scripts/release_is_latest.sh"
RELEASE_FILTER = "startsWith(github.event.release.tag_name, 'naas-abi-v')"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _step_index(steps: list[dict], predicate) -> int:
    return next(i for i, step in enumerate(steps) if predicate(step))


def _runs_rule(step: dict) -> bool:
    return ".github/scripts/release_is_latest.sh" in str(step.get("run") or "")


# --- the workflows ---------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "timeouts"),
    [
        (NEXUS_WEB, {"prepare": 5, "build": 30, "merge": 10}),
        (ABI, {"build": 45}),
    ],
    ids=["nexus-web", "abi"],
)
def test_every_job_keeps_a_timeout(path: Path, timeouts: dict[str, int]) -> None:
    jobs = _load(path)["jobs"]
    assert {name: job.get("timeout-minutes") for name, job in jobs.items()} == timeouts


@pytest.mark.parametrize("path", [NEXUS_WEB, ABI], ids=["nexus-web", "abi"])
def test_images_build_for_naas_abi_releases_only(path: Path) -> None:
    jobs = _load(path)["jobs"]
    gated = "prepare" if "prepare" in jobs else "build"
    assert jobs[gated]["if"] == RELEASE_FILTER
    for name, job in jobs.items():
        if name != gated:
            # A job that needs the gated one skips with it.
            needs = job.get("needs")
            assert gated in ([needs] if isinstance(needs, str) else needs), name


def test_nexus_web_builds_each_platform_natively() -> None:
    workflow = _load(NEXUS_WEB)
    assert "setup-qemu-action" not in NEXUS_WEB.read_text()
    build = workflow["jobs"]["build"]
    assert build["strategy"]["fail-fast"] is True
    assert {
        entry["platform"]: entry["runner"]
        for entry in build["strategy"]["matrix"]["include"]
    } == {"linux/amd64": "ubuntu-24.04", "linux/arm64": "ubuntu-24.04-arm"}
    assert build["runs-on"] == "${{ matrix.runner }}"
    push = next(s for s in build["steps"] if "build-push-action" in s.get("uses", ""))
    assert push["with"]["platforms"] == "${{ matrix.platform }}"
    assert "push-by-digest=true" in push["with"]["outputs"]
    assert "tags" not in push["with"]


def test_nexus_web_tags_only_in_merge_after_both_builds() -> None:
    merge = _load(NEXUS_WEB)["jobs"]["merge"]
    assert set(merge["needs"]) == {"prepare", "build"}
    steps = merge["steps"]
    rule = _step_index(steps, _runs_rule)
    create = _step_index(
        steps, lambda s: "imagetools create" in str(s.get("run") or "")
    )
    check = _step_index(
        steps, lambda s: "imagetools inspect" in str(s.get("run") or "")
    )
    assert rule == create - 1
    assert create < check
    assert "linux/amd64 linux/arm64" in steps[check]["run"]


def test_abi_decides_latest_after_the_build_right_before_the_push() -> None:
    steps = _load(ABI)["jobs"]["build"]["steps"]
    build = _step_index(steps, lambda s: "make build" in str(s.get("run") or ""))
    rule = _step_index(steps, _runs_rule)
    push = _step_index(steps, lambda s: "docker push" in str(s.get("run") or ""))
    assert build < rule == push - 1
    assert "/abi:latest" not in steps[build]["run"]


# --- the :latest rule ------------------------------------------------------

FAKE_GH = """#!/usr/bin/env bash
# Answers the two `gh api` calls of release_is_latest.sh from FAKE_* variables,
# applying the caller's --jq filter like gh does.
path="" filter=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --jq) filter="$2"; shift 2 ;;
    api|--paginate) shift ;;
    *) path="$1"; shift ;;
  esac
done
case "$path" in
  */compare/*)
    [ "${FAKE_FAIL:-}" = compare ] && { echo "gh: Server Error (HTTP 502)" >&2; exit 1; }
    printf '{"status": "%s"}' "$FAKE_COMPARE" | jq -r "$filter" ;;
  */releases*)
    [ "${FAKE_FAIL:-}" = releases ] && { echo "gh: Server Error (HTTP 502)" >&2; exit 1; }
    jq -r "$filter" "$FAKE_RELEASES" ;;
  *) echo "unexpected gh call: $path" >&2; exit 1 ;;
esac
"""


def _release(tag: str, *, draft: bool = False, prerelease: bool = False) -> dict:
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease}


STABLE = [
    _release("naas-abi-v9.9.9"),
    _release("naas-abi-v10.0.0"),
    _release("naas-abi-v4.3.1"),
    _release("naas-abi-v4.3.0"),
    _release("naas-abi-core-v12.0.0"),
    _release("naas-abi-v11.0.0", draft=True),
    _release("naas-abi-v11.0.0-dev.1", prerelease=True),
    _release("naas-abi-v12.0.0", prerelease=True),
]


@pytest.fixture
def rule(tmp_path: Path):
    if not shutil.which("jq") or not shutil.which("bash"):
        pytest.skip("needs bash and jq")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(0o755)

    def run(tag: str, releases: list[dict], compare: str = "ahead", fail: str = ""):
        releases_file = tmp_path / "releases.json"
        releases_file.write_text(json.dumps(releases))
        output = tmp_path / "github_output"
        output.write_text("")
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_COMPARE": compare,
            "FAKE_RELEASES": str(releases_file),
            "FAKE_FAIL": fail,
            "GITHUB_OUTPUT": str(output),
        }
        result = subprocess.run(
            ["bash", str(RULE), tag, "0" * 40, "jupyter-naas/abi"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return result, output.read_text()

    return run


@pytest.mark.parametrize("compare", ["identical", "ahead"])
def test_rule_moves_latest_for_the_highest_release_on_main(rule, compare) -> None:
    result, output = rule("naas-abi-v10.0.0", STABLE, compare=compare)
    assert result.returncode == 0, result.stderr
    assert output == "latest=true\n"


@pytest.mark.parametrize(
    "tag",
    [
        "naas-abi-v9.9.9",  # numerically lower than 10.0.0
        "naas-abi-v4.3.0",  # an older release finishing last, or built again
        "naas-abi-core-v12.0.0",  # another package's release
        "naas-abi-v11.0.0-dev.1",  # a prerelease
        "naas-abi-v12.0.0",  # a release marked prerelease
        "naas-abi-v11.0.0",  # a draft
    ],
)
def test_rule_keeps_latest_for_any_other_release(rule, tag: str) -> None:
    result, output = rule(tag, STABLE)
    assert result.returncode == 0, result.stderr
    assert output == "latest=false\n"


@pytest.mark.parametrize("compare", ["behind", "diverged"])
def test_rule_keeps_latest_for_a_release_main_does_not_contain(rule, compare) -> None:
    result, output = rule("naas-abi-v10.0.0", STABLE, compare=compare)
    assert result.returncode == 0, result.stderr
    assert output == "latest=false\n"


@pytest.mark.parametrize("fail", ["compare", "releases"])
def test_rule_fails_when_github_does_not_answer(rule, fail: str) -> None:
    result, output = rule("naas-abi-v10.0.0", STABLE, fail=fail)
    assert result.returncode != 0
    assert output == ""
