"""What narrowing a module's manifest means (RFC §8.3).

An admin approves what a module asked for, or less. Allow statements may lose
actions and resources; none may gain any or appear; Deny statements stay exactly
as submitted, since dropping one widens what the module may do. The comparison is
on the patterns as written: removing a pattern narrows, rewriting it does not.
"""

from __future__ import annotations

from naas_abi_core.services.iam.policy import PolicyDocument, Statement


def _key(statement: Statement) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return (statement.effect, tuple(sorted(statement.actions)), tuple(sorted(statement.resources)))


def narrowing_errors(submitted: PolicyDocument, narrowed: PolicyDocument) -> list[str]:
    """Why ``narrowed`` is not a narrowing of ``submitted``; empty when it is."""
    errors: list[str] = []
    submitted_deny = sorted(_key(s) for s in submitted.statements if s.effect == "Deny")
    narrowed_deny = sorted(_key(s) for s in narrowed.statements if s.effect == "Deny")
    if submitted_deny != narrowed_deny:
        errors.append("Deny statements cannot be changed: they stay as submitted")
    allows = [s for s in submitted.statements if s.effect == "Allow"]
    for index, statement in enumerate(narrowed.statements, start=1):
        if statement.effect != "Allow":
            continue
        actions, resources = set(statement.actions), set(statement.resources)
        if not any(
            actions <= set(original.actions) and resources <= set(original.resources)
            for original in allows
        ):
            errors.append(
                f"Statement {index} asks for more than the module submitted: "
                "an approval can only remove actions and resources"
            )
    return errors


def is_unchanged(submitted: PolicyDocument, narrowed: PolicyDocument) -> bool:
    return sorted(map(_key, submitted.statements)) == sorted(map(_key, narrowed.statements))
