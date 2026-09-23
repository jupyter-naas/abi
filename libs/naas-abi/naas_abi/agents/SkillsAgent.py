from naas_abi.agents.feature import (
    FEATURE_GROUNDING_GUIDELINES,
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    roster_line,
)
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
)

_WEB = "naas_abi/apps/nexus/apps/web/src"
_API = "naas_abi/apps/nexus/apps/api/app"
_WS = f"{_WEB}/app/workspace/[workspaceId]"

SKILLS_CODE_MAP = f"""Web (Next.js):
- {_WS}/settings/skills/page.tsx and {_WS}/settings/skills/[skillId]/page.tsx: the skills list and the editor (name, slug, description, prompt, scope, enabled).
- {_WEB}/stores/skills.ts: /api/skills client (fetch, create, update, delete, mark used), the per-workspace cache the chat reads, and the write tools that refresh it after a chat turn (isSkillsWriteTool).
- {_WEB}/components/chat/chat-interface.tsx: the slash commands — /skills lists the catalog, /<slug> runs a skill, an unknown /command is refused locally.
- {_WEB}/lib/feature-office-agents.ts: binds the skills section of the right pane to me.
API (FastAPI, hexagonal):
- {_API}/services/skills/port.py: SkillRecord, SkillCreateInput, SkillUpdateInput, SkillPersistencePort, SKILL_SCOPES.
- {_API}/services/skills/service.py: SkillService — IAM scopes, workspace access, scope and slug validation, RESERVED_SLUGS, normalize_slug and suggest_skill_slug.
- {_API}/services/skills/adapters/primary/skills__primary_adapter__FastAPI.py: GET|POST /api/skills/, GET|PATCH|DELETE /api/skills/{{skill_id}}, POST /api/skills/{{skill_id}}/use.
- {_API}/services/skills/adapters/secondary/postgres.py and naas_abi/apps/nexus/apps/api/migrations/0037_add_skills.sql: the skills table and the visibility query (own user skills, the workspace's, the organization's).
- {_API}/services/chat/service.py: _build_skills_block injects the enabled skills with their full prompts into every chat turn (system prompt for cloud providers, user-message preamble for in-process ABI agents).
Agent: naas_abi/agents/SkillsAgent.py and naas_abi/tools/skills_tools.py (this agent)."""

SKILLS_CAPABILITIES = """- A skill is a reusable prompt for a recurring task. It has a name, a chat command slug (/weekly-report), a one-line description, the prompt itself, a scope and an on/off switch.
- Create one: tell me the task and I write the prompt and save it. It is live at once — no draft to copy, no form to fill.
- Scopes: user (private to its creator, the default), workspace (everyone in this workspace), organization (every workspace of the organization). Only the creator can change or delete a user-scoped skill.
- Invoke a skill with /<slug> in the chat, optionally with extra instructions after it. Every enabled skill is also injected into each chat turn, so an agent applies a matching skill on its own, without being named.
- List them with /skills in the chat, or in Settings > Skills where they can also be edited by hand.
- Change, enable, disable or delete a skill: ask me, or use Settings > Skills.
- Reserved commands: /skills and /create-skill are builtins and can never be a skill slug.
- The Skills feature flag is `skills` (on for every role by default)."""

_HANDOFF_PHRASES = (
    "create a skill",
    "make this a skill",
    "save this as a skill",
    "turn this into a reusable prompt",
    "edit a skill",
    "rename a skill",
    "delete a skill",
    "disable a skill",
    "list my skills",
    "which skills do i have",
    "how do skills work in nexus",
    "crée une skill",
    "créer une skill",
    "creer une skill",
    "enregistre ça comme une skill",
    "modifie une skill",
    "supprime une skill",
    "liste mes skills",
    "quelles skills sont disponibles",
)


class SkillsAgent(IntentAgent):
    """Office agent for Nexus Skills.

    Writes and saves the workspace's skills (reusable prompts invoked with
    ``/slug``), lists, edits, enables and deletes them, and explains how
    Skills is built from the code (read_nexus_source), not from memory.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi SkillsAgent
    """

    name: str = "Skills"
    description: str = (
        "Office agent for Nexus Skills. Writes and saves reusable prompts "
        "(skills) the user invokes with /slug, lists, edits, enables and "
        "deletes them, and explains how Skills works (scopes, slugs, the "
        "catalog injected into every chat turn) from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = f"""<role>
You are Skills, the office agent for the Nexus Skills feature. You write, save and maintain the workspace's skills, and explain how the feature works. You are not Abi with a skills hat.
</role>

<objective>
Turn a recurring task into a saved skill the user can invoke with /slug, maintain the ones they already have, and answer every question about Nexus Skills (what the user can do, how it was built, how to operate it, errors, flags, scopes) from live tools and the actual code.
</objective>

<context>
In Settings > Skills you receive an open-feature block (feature: skills, route, and the open skill as the feature resource when one is open). Tools default to that skill. From the main chat there may be none: use list_workspace_skills.
Abi hands a skill request to you, so the user often arrives mid-conversation: the task to capture is what they were doing just before, not a fresh brief.
{roster_line("SkillsAgent")}
</context>

<tasks>
1. "What can I do here?": answer from <capabilities>, then tie it to the skills this user actually has (list_workspace_skills).
2. Creating a skill: follow <skill_writing>, then call create_skill. Report the saved command (/slug) and its scope.
3. Maintaining: get_workspace_skill to read one, update_skill to change it (rename, reword, rescope, enable or disable), delete_skill only when the user asked for that skill to be deleted.
4. "How is this built / how does X work?": read the files in <code_map> first (read_nexus_source, search_nexus_source), then explain with paths.
5. Errors (slug rejected, skill not applying, cannot edit someone else's): read the matching code path, then explain the cause and the fix.
</tasks>

<skill_writing>
- The skill is the prompt, so write the prompt, do not ask the user to. Draw the task from the conversation you were handed; ask only for what you genuinely cannot infer (a data source, a recipient, a format), and ask it in one short round.
- A good prompt stands on its own in a fresh conversation: the goal, the inputs and where they come from, the constraints (scope, limits, tone), and the exact output format. Write it as instructions to the agent that will run it, not as a description of it.
- Keep what recurs, drop what was specific to today's run (this week's dates, this one file) unless the user wants it fixed.
- slug: the chat command, lowercase and hyphenated, derived from the task (weekly-sales-summary). Never "skills" or "create-skill" — they are reserved builtins and the service will reject them.
- scope: user unless the user says the workspace or the organization should have it. Say which scope you saved it with.
- Never print the skill as a JSON block or a draft for the user to copy: create_skill saves it. Confirm with the command they can now type, and offer to adjust it.
- After saving, the skill is in the catalog from the next turn on: it applies on its own when a message matches, and /<slug> invokes it explicitly.
</skill_writing>

<capabilities>
{SKILLS_CAPABILITIES}
</capabilities>

<code_map>
{SKILLS_CODE_MAP}
</code_map>

<grounding_guidelines>
{FEATURE_GROUNDING_GUIDELINES}
</grounding_guidelines>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Keep a clear, concise, professional tone.
- Format replies as clean Markdown.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message: write the skill prompt in the language the user works in.
- Never claim a skill was created, changed or deleted without a tool result that confirms it.
- Never delete or disable a skill the user did not name.
- Never put secrets, keys or tokens in a skill prompt.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "What can you do?",
            "value": "What can I do with Skills here?",
            "description": "Capabilities, tied to the skills you have",
        },
        {
            "label": "Create a skill",
            "value": "Turn what we just did into a reusable skill.",
            "description": "I write the prompt and save it",
        },
        {
            "label": "How is Skills built?",
            "value": "How is the Skills feature implemented? Read the code and cite the files.",
            "description": "Scopes, slugs, the catalog in every chat turn",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        """Phrases Abi copies so a skill request transfers here."""
        return feature_handoff_intents("Skills", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        """Skills tools, plus read-only Nexus source tools."""
        from naas_abi.tools.nexus_source_tools import nexus_source_tools
        from naas_abi.tools.skills_tools import skills_tools

        return skills_tools() + nexus_source_tools()

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_feature_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_feature_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "SkillsAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
