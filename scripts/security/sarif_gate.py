"""Gate CI on SARIF findings that are new relative to a committed baseline.

Every scanner in `.github/workflows/security*.yml` emits SARIF. This script
reads those reports, classifies each result by severity, and fails when a
result at or above `--min-severity` is not listed in the tool's baseline.

Existing findings are recorded in `.github/security/baselines/<tool>.json`
(`--write-baseline`), so the gate blocks *new* holes without first requiring
every historical finding to be fixed. Shrink the baselines as debt is paid.

Fingerprints ignore line numbers (they drift on unrelated edits) and hash the
rule id, file path and message instead.

Stdlib only: runs on any runner with a Python 3.10+ interpreter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

SEVERITIES = ("low", "medium", "high", "critical")

_LEVEL_TO_SEVERITY = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "low",
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    uri: str
    line: int | None
    message: str
    severity: str

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256(
            f"{self.rule_id}|{self.uri}|{self.message}".encode()
        ).hexdigest()
        return digest[:20]

    @property
    def label(self) -> str:
        return f"{self.rule_id} {self.uri}"


def severity_from_score(score: float) -> str:
    """Map a CVSS-style `security-severity` score to a severity bucket."""
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def _rule_properties(run: dict, result: dict) -> dict:
    rules = run.get("tool", {}).get("driver", {}).get("rules", []) or []
    index = result.get("ruleIndex")
    if isinstance(index, int) and 0 <= index < len(rules):
        return rules[index].get("properties", {}) or {}
    rule_id = result.get("ruleId")
    for rule in rules:
        if rule.get("id") == rule_id:
            return rule.get("properties", {}) or {}
    return {}


def _rule_default_level(run: dict, result: dict) -> str | None:
    rules = run.get("tool", {}).get("driver", {}).get("rules", []) or []
    rule_id = result.get("ruleId")
    for rule in rules:
        if rule.get("id") == rule_id:
            return (rule.get("defaultConfiguration") or {}).get("level")
    return None


def classify(run: dict, result: dict) -> str:
    """Severity of one SARIF result.

    `security-severity` (CVSS score, used by CodeQL/Trivy/OSV) wins over the
    generic SARIF `level`, which is all most linters provide.
    """
    for props in (result.get("properties", {}) or {}, _rule_properties(run, result)):
        score = props.get("security-severity")
        if score is not None:
            try:
                return severity_from_score(float(score))
            except (TypeError, ValueError):
                pass
    level = result.get("level") or _rule_default_level(run, result) or "warning"
    return _LEVEL_TO_SEVERITY.get(level, "medium")


def parse_sarif(document: dict) -> list[Finding]:
    findings: list[Finding] = []
    for run in document.get("runs", []) or []:
        for result in run.get("results", []) or []:
            if result.get("suppressions"):
                continue
            location = (result.get("locations") or [{}])[0].get("physicalLocation", {})
            uri = location.get("artifactLocation", {}).get("uri", "")
            line = location.get("region", {}).get("startLine")
            findings.append(
                Finding(
                    rule_id=str(result.get("ruleId", "unknown")),
                    uri=uri,
                    line=line,
                    message=(result.get("message", {}) or {}).get("text", "").strip(),
                    severity=classify(run, result),
                )
            )
    return findings


def load_baseline(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return set(json.loads(path.read_text()).get("fingerprints", {}))


def write_baseline(path: Path, tool: str, findings: list[Finding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = {f.fingerprint: f.label for f in findings}
    payload = {"tool": tool, "fingerprints": dict(sorted(entries.items()))}
    path.write_text(json.dumps(payload, indent=2) + "\n")


def at_or_above(severity: str, threshold: str) -> bool:
    return SEVERITIES.index(severity) >= SEVERITIES.index(threshold)


def _summary(tool: str, blocking: list[Finding], known: int, total: int) -> str:
    lines = [
        f"### {tool}",
        "",
        (
            f"{total} finding(s) total, {known} already in baseline, "
            f"**{len(blocking)} new blocking**."
        ),
    ]
    if blocking:
        lines += ["", "| Severity | Rule | Location | Message |", "|---|---|---|---|"]
        for f in blocking[:100]:
            where = f"{f.uri}:{f.line}" if f.line else f.uri
            message = f.message.replace("|", "\\|").replace("\n", " ")[:160]
            lines.append(f"| {f.severity} | `{f.rule_id}` | `{where}` | {message} |")
        if len(blocking) > 100:
            lines.append(f"| … | {len(blocking) - 100} more | | |")
    return "\n".join(lines) + "\n\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sarif", nargs="+", type=Path, help="SARIF report(s)")
    parser.add_argument("--tool", required=True, help="Name used in output")
    parser.add_argument("--min-severity", choices=SEVERITIES, default="high")
    parser.add_argument("--baseline", type=Path, help="Baseline JSON to diff against")
    parser.add_argument(
        "--write-baseline",
        type=Path,
        help="Record every current finding (all severities) as the new baseline",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "Print counts only. Use for findings against a running deployment: "
            "logs of a public repo are world-readable, the Security tab is not."
        ),
    )
    args = parser.parse_args(argv)

    # Fail closed: a scanner that crashed before writing its report must not
    # read as "no findings".
    findings: list[Finding] = []
    for report in args.sarif:
        try:
            document = json.loads(report.read_text())
        except (OSError, json.JSONDecodeError) as error:
            print(f"::error::{args.tool}: unreadable report {report}: {error}")
            return 2
        findings.extend(parse_sarif(document))

    if args.write_baseline:
        write_baseline(args.write_baseline, args.tool, findings)
        print(
            f"{args.tool}: wrote {len(findings)} fingerprint(s) to {args.write_baseline}"
        )
        return 0

    baseline = load_baseline(args.baseline)
    known = [f for f in findings if f.fingerprint in baseline]
    blocking = [
        f
        for f in findings
        if f.fingerprint not in baseline and at_or_above(f.severity, args.min_severity)
    ]

    for f in [] if args.quiet else blocking:
        location = f"file={f.uri},line={f.line}" if f.line else f"file={f.uri}"
        title = f"{args.tool} {f.severity}: {f.rule_id}"
        print(f"::error {location},title={title}::{f.message[:300]}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as handle:
            listed = [] if args.quiet else blocking
            handle.write(_summary(args.tool, listed, len(known), len(findings)))
            if args.quiet and blocking:
                handle.write(
                    f"{len(blocking)} new blocking finding(s), details in the "
                    "Security tab (code scanning).\n\n"
                )

    print(
        f"{args.tool}: {len(findings)} total, {len(known)} baselined, "
        f"{len(blocking)} new at >= {args.min_severity}"
    )
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
