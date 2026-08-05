from __future__ import annotations

from typing import Any

from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.gatekeeper.GatekeeperPort import (
    GatekeeperDecision,
    GatekeeperResource,
    GatekeeperSubject,
    IGatekeeperDomain,
    IGatekeeperPolicy,
    IGrantStore,
    IObservationStore,
    ObservationRecord,
    ResourceGrant,
    new_observation_id,
    utc_now,
)
from naas_abi_core.services.gatekeeper.policies.GitHubGatekeeperPolicy import (
    GITHUB_TOOL_PREFIX,
    GitHubGatekeeperPolicy,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class GatekeeperService(ServiceBase, IGatekeeperDomain):
    """Mediate tool access, record observations, and enforce derivation policy."""

    def __init__(
        self,
        observation_store: IObservationStore,
        grant_store: IGrantStore,
        policies: list[IGatekeeperPolicy] | None = None,
        activity_log: ActivityLogService | None = None,
    ) -> None:
        super().__init__()
        self._observations = observation_store
        self._grants = grant_store
        self._policies = policies or [GitHubGatekeeperPolicy()]
        self._activity_log = activity_log

    def evaluate_tool_call(
        self,
        subject: GatekeeperSubject,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> GatekeeperDecision:
        args = tool_args or {}
        policy = self._policy_for_tool(tool_name)
        if policy is None:
            return GatekeeperDecision(allowed=True, reason="no_policy")

        sensitivity = policy.classify_tool(tool_name)
        if sensitivity != "sensitive":
            return GatekeeperDecision(allowed=True, reason="not_sensitive")

        chat_id = subject.chat_id
        if not chat_id:
            decision = GatekeeperDecision(
                allowed=False,
                reason="sensitive_tool_requires_chat_session",
            )
            self._audit(subject, "gatekeeper.tool.denied", tool_name, decision.reason)
            return decision

        resources = policy.extract_resources(tool_name, args)
        if not resources:
            decision = GatekeeperDecision(
                allowed=False,
                reason="sensitive_tool_missing_resource_scope",
            )
            self._audit(subject, "gatekeeper.tool.denied", tool_name, decision.reason)
            return decision

        action = policy.required_action(tool_name)
        for resource in resources:
            if not self._grants.has_grant(chat_id, resource.type, resource.id, action):
                decision = GatekeeperDecision(
                    allowed=False,
                    reason=(f"missing_grant:{resource.type}:{resource.id}:{action}"),
                )
                self._audit(
                    subject, "gatekeeper.tool.denied", tool_name, decision.reason
                )
                return decision

        decision = GatekeeperDecision(allowed=True, reason="granted")
        self._audit(subject, "gatekeeper.tool.allowed", tool_name, decision.reason)
        return decision

    def record_tool_observation(
        self,
        subject: GatekeeperSubject,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> ObservationRecord | None:
        args = tool_args or {}
        policy = self._policy_for_tool(tool_name)
        if policy is None or not subject.chat_id:
            return None

        resources = policy.extract_resources(tool_name, args)
        if not resources:
            resources = [GatekeeperResource(type="tool", id=tool_name)]

        sensitivity = policy.classify_tool(tool_name)
        observation = ObservationRecord(
            id=new_observation_id(),
            chat_id=subject.chat_id,
            user_id=subject.user_id,
            workspace_id=subject.workspace_id,
            tool_name=tool_name,
            resource_type=resources[0].type,
            resource_id=resources[0].id,
            sensitivity=sensitivity,
            observed_at=utc_now(),
            tool_args=args,
        )
        try:
            self._observations.record(observation)
        except Exception as exc:  # noqa: BLE001
            from naas_abi_core import logger

            logger.warning(f"gatekeeper.record_observation failed: {exc}")
            return None

        if sensitivity == "sensitive":
            for resource in resources:
                self.grant_resource(
                    subject.chat_id,
                    resource,
                    frozenset({"export"}),
                )

        self._audit(
            subject,
            "gatekeeper.observation.recorded",
            tool_name,
            f"{observation.resource_type}:{observation.resource_id}",
        )
        return observation

    def grant_resource(
        self,
        chat_id: str,
        resource: GatekeeperResource,
        actions: frozenset[str],
    ) -> ResourceGrant:
        grant = ResourceGrant(
            chat_id=chat_id,
            resource_type=resource.type,
            resource_id=resource.id,
            actions=actions,
            granted_at=utc_now(),
        )
        self._grants.grant(grant)
        return grant

    def evaluate_conversation_export(
        self,
        subject: GatekeeperSubject,
        conversation_id: str,
    ) -> GatekeeperDecision:
        sensitive = [
            obs
            for obs in self._observations.list_observations(conversation_id)
            if obs.sensitivity == "sensitive"
        ]
        if not sensitive:
            return GatekeeperDecision(allowed=True, reason="no_sensitive_observations")

        for obs in sensitive:
            if subject.user_id != obs.user_id:
                decision = GatekeeperDecision(
                    allowed=False,
                    reason=(
                        "export_denied:viewer_lacks_access_to_observed_resource:"
                        f"{obs.resource_type}:{obs.resource_id}"
                    ),
                )
                self._audit(
                    subject,
                    "gatekeeper.export.denied",
                    conversation_id,
                    decision.reason,
                )
                return decision

            if not self._grants.has_grant(
                conversation_id, obs.resource_type, obs.resource_id, "export"
            ) and not self._grants.has_grant(
                conversation_id, obs.resource_type, obs.resource_id, "*"
            ):
                decision = GatekeeperDecision(
                    allowed=False,
                    reason=(
                        "export_denied:sensitive_observations_require_export_grant:"
                        f"{obs.resource_type}:{obs.resource_id}"
                    ),
                )
                self._audit(
                    subject,
                    "gatekeeper.export.denied",
                    conversation_id,
                    decision.reason,
                )
                return decision

        return GatekeeperDecision(allowed=True, reason="export_granted")

    def list_observations(self, chat_id: str) -> list[ObservationRecord]:
        return self._observations.list_observations(chat_id)

    def shutdown(self) -> None:
        self._observations.shutdown()
        self._grants.shutdown()

    def _policy_for_tool(self, tool_name: str) -> IGatekeeperPolicy | None:
        if not tool_name.startswith(GITHUB_TOOL_PREFIX):
            return None
        for policy in self._policies:
            if isinstance(policy, GitHubGatekeeperPolicy):
                return policy
        return self._policies[0] if self._policies else None

    def _audit(
        self,
        subject: GatekeeperSubject,
        event_type: str,
        tool_name: str,
        reason: str,
    ) -> None:
        if self._activity_log is None:
            return
        actor_id = f"user:{subject.user_id}" if subject.user_id else "anonymous"
        self._activity_log.record(
            ActivityEvent(
                actor_id=actor_id,
                event_type=event_type,
                correlation_id=subject.chat_id,
                attributes={
                    "tool_name": tool_name,
                    "reason": reason,
                    "workspace_id": subject.workspace_id,
                },
            )
        )
