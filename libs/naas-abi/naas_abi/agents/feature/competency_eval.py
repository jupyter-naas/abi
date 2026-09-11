"""Run the feature-agent competency questions against a live engine.

Each question is asked twice: to the feature office agent with its feature
context (the right pane on that section), and to an orchestrator with no
feature context (Home or Chat). The orchestrator is Abi by default; pass
``--orchestrator`` to test another one that reaches the feature agents, such
as Bob through Abi. Tool calls are recorded for the agent and, for the
orchestrator, for every sub-agent it hands off to, then graded by
``competency.grade``.

Run it where the config's services resolve (inside the API container)::

    ENV=local python -m naas_abi.agents.feature.competency_eval \\
        --workspace <workspace_id> --user <user_id> \\
        [--agents Apps,Files] [--via feature|abi|both] [--out report.jsonl] \\
        [--orchestrator bob.agents.BobAgent:BobAgent --modules naas_abi,bob]

It calls the configured model once or more per question: it costs tokens.
"""

from __future__ import annotations

import argparse
import contextvars
import json
import sys
import time
from collections.abc import Callable
from typing import Any

from naas_abi.agents.feature.competency import (
    COMPETENCY_QUESTIONS,
    CompetencyQuestion,
    grade,
)
from naas_abi.agents.feature.registry import FEATURE_AGENTS, FeatureAgentSpec

_EXCERPT = 600
ABI_ORCHESTRATOR = "naas_abi.agents.AbiAgent:AbiAgent"


def load_orchestrator(ref: str) -> Any:
    """The agent class at ``module:Class``."""
    import importlib

    module, _, name = ref.partition(":")
    if not module or not name:
        raise ValueError(f"expected module:Class, got {ref!r}")
    return getattr(importlib.import_module(module), name)


def _tool_names(message: Any) -> list[str]:
    names: list[str] = []
    for call in getattr(message, "tool_calls", None) or []:
        name = (
            call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
        )
        if name:
            names.append(str(name))
    return names


def _watch_tools(agent: Any, sink: list[str]) -> None:
    """Record tool calls of ``agent`` and of every sub-agent it can hand off to."""
    seen: set[int] = set()

    def _attach(node: Any) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        node.on_tool_usage(lambda message: sink.extend(_tool_names(message)))
        for child in getattr(node, "_agents", None) or []:
            _attach(child)

    _attach(agent)


def _feature_context(spec: FeatureAgentSpec, workspace_id: str) -> dict[str, Any]:
    key = spec.feature_keys[0]
    route = {"graph": "graph/network", "agents": "settings/agents"}.get(
        key, key.split(".")[0]
    )
    return {"key": key, "path": f"/workspace/{workspace_id}/{route}"}


def collect_stream(events: Any) -> str:
    """The reply the pane shows, assembled like the API's in-process stream
    (``provider_runtime``): every ``ai_message`` (sub-agents included, they
    share the queue), else the closing ``message`` replay."""
    messages: list[str] = []
    replay: list[str] = []
    for event in events:
        if isinstance(event, str):
            if event.strip():
                messages.append(event)
            continue
        if not isinstance(event, dict):
            continue
        name = str(event.get("event", "")).strip()
        text = "" if event.get("data") is None else str(event.get("data"))
        if text == "[DONE]" or name == "done":
            break
        if name == "ai_message" and text.strip():
            messages.append(text.strip())
        elif name == "message" and text.strip():
            replay.append(text.strip())
    return "\n\n".join(messages) if messages else "\n".join(replay)


def _fresh(template: Any) -> Any:
    """Per-question copy with fresh state, like the API's per-request duplicate
    (``provider_runtime._duplicate_inprocess_agent``): no sticky active agent
    or thread from the previous question."""
    from queue import Queue
    from uuid import uuid4

    from naas_abi_core.services.agent.Agent import AgentSharedState

    supervisor = getattr(getattr(template, "state", None), "supervisor_agent", None)
    return template.duplicate(
        queue=Queue(),
        agent_shared_state=AgentSharedState(
            thread_id=uuid4().hex, supervisor_agent=supervisor
        ),
    )


def ask(
    template: Any,
    question: CompetencyQuestion,
    *,
    user_id: str,
    workspace_id: str,
    feature_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """One question in a fresh request context; returns the graded record."""
    from naas_abi.agents.feature.context import nexus_feature_context
    from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

    agent = _fresh(template)
    tools: list[str] = []
    _watch_tools(agent, tools)

    def _run() -> tuple[str, str | None]:
        agent_user_id.set(user_id)
        agent_workspace_id.set(workspace_id)
        nexus_feature_context.set(feature_context)
        try:
            return collect_stream(agent.stream_invoke(question.question)), None
        except Exception as exc:  # noqa: BLE001
            return "", f"{type(exc).__name__}: {exc}"[:300]

    started = time.time()
    answer, error = contextvars.copy_context().run(_run)
    result = grade(question, answer, tools, error)
    return {
        "question": question.question,
        "kind": question.kind,
        "passed": result.passed,
        "reasons": result.reasons,
        "tools": tools,
        "seconds": round(time.time() - started, 1),
        "answer": answer[:_EXCERPT],
    }


def run(
    specs: list[FeatureAgentSpec],
    *,
    user_id: str,
    workspace_id: str,
    via: str,
    emit: Callable[[dict[str, Any]], None],
    orchestrator: str = ABI_ORCHESTRATOR,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    abi = None
    abi_label = "abi"
    if via in {"abi", "both"}:
        abi = load_orchestrator(orchestrator).New()
        abi_label = str(abi.name).lower()
    for spec in specs:
        questions = COMPETENCY_QUESTIONS.get(spec.name, ())
        targets: list[tuple[str, Any, dict[str, Any] | None]] = []
        if via in {"feature", "both"}:
            targets.append(
                ("feature", spec.load().New(), _feature_context(spec, workspace_id))
            )
        if abi is not None:
            targets.append((abi_label, abi, None))
        for via_name, agent, feature_context in targets:
            for question in questions:
                record = ask(
                    agent,
                    question,
                    user_id=user_id,
                    workspace_id=workspace_id,
                    feature_context=feature_context,
                )
                record.update({"agent": spec.name, "via": via_name})
                records.append(record)
                emit(record)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument(
        "--agents", default="", help="Comma-separated agent names (default: all)"
    )
    parser.add_argument(
        "--via",
        choices=("feature", "abi", "both"),
        default="both",
        help="abi: through the orchestrator (see --orchestrator)",
    )
    parser.add_argument("--out", default="", help="Append JSON lines here")
    parser.add_argument(
        "--orchestrator",
        default=ABI_ORCHESTRATOR,
        help="module:Class of the orchestrator (default: Abi)",
    )
    parser.add_argument(
        "--modules",
        default="naas_abi",
        help="Comma-separated engine modules to load (the orchestrator's module too)",
    )
    args = parser.parse_args(argv)

    wanted = {name.strip() for name in args.agents.split(",") if name.strip()}
    specs = [
        s
        for s in FEATURE_AGENTS
        if not wanted or s.name in wanted or s.class_name in wanted
    ]
    if wanted and not specs:
        parser.error(f"unknown agents: {sorted(wanted)}")

    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=[m.strip() for m in args.modules.split(",") if m.strip()])

    out = open(args.out, "a", encoding="utf-8") if args.out else None

    def _emit(record: dict[str, Any]) -> None:
        mark = "PASS" if record["passed"] else "FAIL"
        print(
            f"[{mark}] {record['via']:<7} {record['agent']:<15} {record['kind']:<14} "
            f"{record['seconds']:>6}s  {record['question'][:70]}",
            flush=True,
        )
        if not record["passed"]:
            print(
                f"        reasons: {record['reasons']}  tools: {record['tools']}",
                flush=True,
            )
        if out is not None:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

    try:
        records = run(
            specs,
            user_id=args.user,
            workspace_id=args.workspace,
            via=args.via,
            emit=_emit,
            orchestrator=args.orchestrator,
        )
    finally:
        if out is not None:
            out.close()
    failed = [r for r in records if not r["passed"]]
    print(f"\n{len(records) - len(failed)}/{len(records)} passed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
