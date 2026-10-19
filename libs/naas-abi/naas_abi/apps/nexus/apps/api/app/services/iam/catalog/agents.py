"""Agents and skills of a workspace."""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("agent"), rtype("skill"))

ACTIONS = (
    # Reading the roster is what the chat picker does for every role: the
    # "agents" feature is the settings section, which only changes them.
    action("ListAgents", "list", "agent"),
    action("GetAgent", "read", "agent"),
    action("CreateAgent", "write", "agent", feature="agents"),
    action("UpdateAgent", "write", "agent", feature="agents"),
    action("DeleteAgent", "write", "agent", feature="agents"),
    # Reconciles the roster with the modules' agents. Every client sends it once
    # per session, so it stays with the members who may write; for a viewer the
    # route answers with the listing alone.
    action("SyncAgents", "write", "agent"),
    # Invoking an agent in chat or through ``/v1``.
    action("UseAgent", "read", "agent"),
    action("ListSkills", "list", "skill", feature="skills"),
    action("GetSkill", "read", "skill", feature="skills"),
    action("CreateSkill", "write", "skill", feature="skills"),
    action("UpdateSkill", "write", "skill", feature="skills"),
    action("DeleteSkill", "write", "skill", feature="skills"),
    # Stamps ``last_used_at`` when a skill is invoked from the chat.
    action("MarkSkillUsed", "write", "skill", feature="skills"),
    action("UseSkill", "read", "skill"),
)
