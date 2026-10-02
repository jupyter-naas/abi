import json
from pathlib import Path

import pytest
from sarif_gate import (
    Finding,
    classify,
    main,
    parse_sarif,
    severity_from_score,
)


def _sarif(results: list[dict], rules: list[dict] | None = None) -> dict:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "t", "rules": rules or []}},
                "results": results,
            }
        ],
    }


def _result(rule_id: str, uri: str = "a.py", level: str | None = None, **extra) -> dict:
    result = {
        "ruleId": rule_id,
        "message": {"text": f"msg {rule_id}"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {"startLine": 3},
                }
            }
        ],
        **extra,
    }
    if level:
        result["level"] = level
    return result


@pytest.mark.parametrize(
    ("score", "expected"),
    [(9.8, "critical"), (7.0, "high"), (5.3, "medium"), (1.0, "low")],
)
def test_severity_from_score(score, expected):
    assert severity_from_score(score) == expected


def test_security_severity_on_rule_wins_over_level():
    run = {
        "tool": {
            "driver": {
                "rules": [{"id": "R", "properties": {"security-severity": "9.1"}}]
            }
        }
    }
    assert classify(run, {"ruleId": "R", "level": "note"}) == "critical"


def test_level_used_when_no_score():
    assert (
        classify({"tool": {"driver": {}}}, {"ruleId": "R", "level": "error"}) == "high"
    )


def test_rule_default_level_used_when_result_has_none():
    run = {
        "tool": {
            "driver": {
                "rules": [{"id": "R", "defaultConfiguration": {"level": "note"}}]
            }
        }
    }
    assert classify(run, {"ruleId": "R"}) == "low"


def test_suppressed_results_are_ignored():
    doc = _sarif([_result("R", level="error", suppressions=[{"kind": "inSource"}])])
    assert parse_sarif(doc) == []


def test_fingerprint_ignores_line_numbers():
    a = Finding("R", "a.py", 3, "m", "high")
    b = Finding("R", "a.py", 99, "m", "high")
    assert a.fingerprint == b.fingerprint


def test_gate_fails_on_new_high_and_passes_once_baselined(tmp_path: Path):
    report = tmp_path / "r.sarif"
    report.write_text(json.dumps(_sarif([_result("R1", level="error")])))
    baseline = tmp_path / "baseline.json"

    assert main([str(report), "--tool", "t", "--baseline", str(baseline)]) == 1

    assert main([str(report), "--tool", "t", "--write-baseline", str(baseline)]) == 0
    assert main([str(report), "--tool", "t", "--baseline", str(baseline)]) == 0


def test_gate_ignores_findings_below_threshold(tmp_path: Path):
    report = tmp_path / "r.sarif"
    report.write_text(json.dumps(_sarif([_result("R1", level="warning")])))
    assert main([str(report), "--tool", "t", "--min-severity", "high"]) == 0
    assert main([str(report), "--tool", "t", "--min-severity", "medium"]) == 1


def test_new_finding_fails_even_with_baseline_present(tmp_path: Path):
    old = tmp_path / "old.sarif"
    old.write_text(json.dumps(_sarif([_result("R1", level="error")])))
    baseline = tmp_path / "baseline.json"
    main([str(old), "--tool", "t", "--write-baseline", str(baseline)])

    new = tmp_path / "new.sarif"
    new.write_text(
        json.dumps(
            _sarif([_result("R1", level="error"), _result("R2", "b.py", level="error")])
        )
    )
    assert main([str(new), "--tool", "t", "--baseline", str(baseline)]) == 1


def test_missing_report_fails_closed(tmp_path: Path):
    assert main([str(tmp_path / "absent.sarif"), "--tool", "t"]) == 2


def test_corrupt_report_fails_closed(tmp_path: Path):
    report = tmp_path / "r.sarif"
    report.write_text("{not json")
    assert main([str(report), "--tool", "t"]) == 2


def test_quiet_mode_still_fails_but_prints_no_details(tmp_path: Path, capsys):
    report = tmp_path / "r.sarif"
    report.write_text(json.dumps(_sarif([_result("R1", "secret.py", level="error")])))
    assert main([str(report), "--tool", "t", "--quiet"]) == 1
    out = capsys.readouterr().out
    assert "secret.py" not in out
    assert "msg R1" not in out
