#!/usr/bin/env python3
"""
Generate individual Turtle ontology files for each NEXUS process.
Each process gets its own file with full BFO 7 Buckets structure.
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class ProcessDef:
    """Definition of a NEXUS process."""

    name: str
    label: str
    definition: str
    implementation: str
    folder: str
    example: str = ""


# Define all processes
PROCESSES = [
    # Authentication processes
    ProcessDef(
        name="UserLoginProcess",
        label="User Login Process",
        definition="A process that authenticates a user's credentials and issues JWT access tokens and refresh tokens for session management.",
        implementation="apps/api/app/api/endpoints/auth.py lines 344-389",
        folder="authentication",
        example="User submits email + password → System verifies credentials → Issues access token (15min) + refresh token (30d) → Logs audit event",
    ),
    ProcessDef(
        name="TokenRefreshProcess",
        label="Token Refresh Process",
        definition="A process that validates a refresh token and issues new access and refresh tokens, implementing token rotation for enhanced security.",
        implementation="apps/api/app/api/endpoints/auth.py lines 512-542, apps/api/app/services/refresh_token.py",
        folder="authentication",
        example="Client sends refresh token → System validates hash & expiry → Issues new access token + new refresh token → Revokes old refresh token",
    ),
    ProcessDef(
        name="TokenRevocationProcess",
        label="Token Revocation Process",
        definition="A process that invalidates authentication tokens by marking them as revoked in the revoked_tokens or refresh_tokens table.",
        implementation="apps/api/app/services/refresh_token.py lines 135-204",
        folder="authentication",
        example="User logs out / Password changed / Security breach → System adds JTI to revoked_tokens → Future requests with that token rejected",
    ),
    ProcessDef(
        name="PasswordChangeProcess",
        label="Password Change Process",
        definition="A process that updates a user's password, revokes all existing sessions, and logs the security event for audit purposes.",
        implementation="apps/api/app/api/endpoints/auth.py lines 551-604",
        folder="authentication",
        example="User provides current + new password → System verifies current → Hashes new → Updates DB → Revokes all tokens → Logs event",
    ),
    ProcessDef(
        name="WorkspaceAccessControlProcess",
        label="Workspace Access Control Process",
        definition="A process that validates whether a user has permission to access a workspace resource based on their role (owner/admin/member/viewer).",
        implementation="apps/api/app/api/endpoints/auth.py lines 226-260",
        folder="authentication",
        example="User requests workspace resource → System checks workspace_members table → Returns role or raises 403",
    ),
    ProcessDef(
        name="RateLimitingProcess",
        label="Rate Limiting Process",
        definition="A process that prevents brute force attacks by tracking and limiting the number of authentication attempts per time window.",
        implementation="apps/api/app/services/rate_limit.py lines 16-64",
        folder="authentication",
        example="Auth request arrives → System counts attempts in 15min window → If > 5: reject with 429 → Else: allow & record attempt",
    ),
    ProcessDef(
        name="AuditLoggingProcess",
        label="Audit Logging Process",
        definition="A process that records sensitive operations (login, password changes, token events) to the audit_logs table for compliance and forensics.",
        implementation="apps/api/app/services/audit.py lines 16-109",
        folder="authentication",
        example="Security event occurs → System captures action, user_id, IP, user-agent, timestamp → Inserts to audit_logs table",
    ),
    # Chat & Conversation processes
    ProcessDef(
        name="ChatCompletionProcess",
        label="Chat Completion Process",
        definition="A process that generates an AI assistant response to a user message by routing to configured LLM provider (OpenAI, Anthropic, Ollama, Cloudflare, ABI).",
        implementation="apps/api/app/api/endpoints/chat.py lines 544-623",
        folder="chat_conversation",
        example="User sends message → System resolves provider → Builds prompt with history → Calls LLM API → Saves assistant response",
    ),
    ProcessDef(
        name="ChatStreamingProcess",
        label="Chat Streaming Process",
        definition="A process that streams AI responses in real-time using Server-Sent Events (SSE), delivering tokens incrementally as they are generated.",
        implementation="apps/api/app/api/endpoints/chat.py lines 626-773",
        folder="chat_conversation",
        example='User sends message → System streams SSE → data: {\\"content\\": \\"token\\"} → data: [DONE] → Saves complete response',
    ),
    ProcessDef(
        name="MultiAgentConversationProcess",
        label="Multi-Agent Conversation Process",
        definition="A process that manages conversations involving multiple AI agents, injecting agent identity markers to prevent confusion and maintain context.",
        implementation="apps/api/app/api/endpoints/chat.py lines 368-431",
        folder="chat_conversation",
        example="Multiple agents in history → System injects --- Agent: AgentName --- markers → Prevents identity confusion",
    ),
    ProcessDef(
        name="ConversationCreationProcess",
        label="Conversation Creation Process",
        definition="A process that creates a new conversation entity with workspace association, default title, and timestamp initialization.",
        implementation="apps/api/app/api/endpoints/chat.py lines 476-827",
        folder="chat_conversation",
        example="User starts chat → System generates conversation_id → Sets workspace_id → Creates DB record → Returns conversation",
    ),
    ProcessDef(
        name="MessagePersistenceProcess",
        label="Message Persistence Process",
        definition="A process that stores user and assistant messages in the messages table with conversation linkage, role attribution, and timestamp tracking.",
        implementation="apps/api/app/api/endpoints/chat.py (implicit in all chat endpoints)",
        folder="chat_conversation",
        example="Message generated → System inserts to messages table → Links to conversation_id → Sets role (user/assistant/system)",
    ),
    ProcessDef(
        name="WebSearchIntegrationProcess",
        label="Web Search Integration Process",
        definition="A process that performs external web searches (Wikipedia, DuckDuckGo) and injects results as context into chat prompts.",
        implementation="apps/api/app/api/endpoints/chat.py lines 434-471",
        folder="chat_conversation",
        example="User message detected as search query → System calls Wikipedia + DuckDuckGo APIs → Injects results as context → LLM generates response",
    ),
    ProcessDef(
        name="ProviderRoutingProcess",
        label="Provider Routing Process",
        definition="A process that resolves which LLM provider to use based on agent configuration, workspace secrets, and model availability.",
        implementation="apps/api/app/api/endpoints/chat.py lines 202-319",
        folder="chat_conversation",
        example="Agent selected → System checks agent.provider → Loads API key from secrets → Selects model based on capabilities (vision support)",
    ),
]


def generate_process_file(proc: ProcessDef, output_dir: Path):
    """Generate a Turtle file for a single process."""
    name_snake = "".join(
        ["_" + c.lower() if c.isupper() else c for c in proc.name]
    ).lstrip("_")
    filename = f"{name_snake}.ttl"
    filepath = output_dir / proc.folder / filename

    # Ensure folder exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    content = f'''@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dc: <http://purl.org/dc/terms/> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix nexus: <http://nexus.platform/ontology/> .

# ======================================================================
# {proc.label}
# BFO 7 Buckets Compliant (ISO 21383-2)
# ======================================================================

nexus:{name_snake}_ontology a owl:Ontology ;
    dc:title "{proc.label}"@en ;
    dc:description "{proc.definition}"@en ;
    dc:created "2026-02-09"^^xsd:date ;
    owl:imports <http://ontology.naas.ai/abi/BFO7Buckets> ,
                <http://nexus.platform/ontology/_shared/common_entities> .

# ======================================================================
# WHAT: Process (BFO_0000015)
# ======================================================================

nexus:{proc.name} a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000015 ;
    rdfs:label "{proc.label}"@en ;
    skos:definition "{proc.definition}"@en ;
    rdfs:comment "Implements: {proc.implementation}" ;
'''

    if proc.example:
        content += f'    skos:example "{proc.example}"@en .\n'
    else:
        content += "    .\n"

    content += f"""
# ======================================================================
# WHO, WHERE, WHEN, HOW WE KNOW, HOW IT IS, WHY
# TODO: Add specific entities, qualities, roles, and relationships
# ======================================================================

# Use this template to add process-specific BFO entities:
# - WHO (BFO_0000040): Material entities that participate
# - WHERE (BFO_0000029): Sites where process occurs
# - WHEN (BFO_0000008): Temporal regions
# - HOW WE KNOW (BFO_0000031): Information entities
# - HOW IT IS (BFO_0000019): Qualities
# - WHY (BFO_0000023/BFO_0000016): Roles and dispositions

# Example instance (replace with actual data):
nexus:example_{name_snake}_instance a nexus:{proc.name} ;
    dc:created "2026-02-09T15:00:00Z"^^xsd:dateTime ;
    rdfs:label "Example {proc.label} Instance"@en .
"""

    filepath.write_text(content)
    print(f"✓ Generated: {filepath.relative_to(output_dir)}")


def main():
    output_dir = Path(__file__).parent.parent / "processes"

    print(f"Generating process ontologies in: {output_dir}")
    print(f"Total processes: {len(PROCESSES)}\n")

    for proc in PROCESSES:
        generate_process_file(proc, output_dir)

    print(f"\n✓ Generated {len(PROCESSES)} process ontology files")
    print("\nFolder structure:")
    for folder in sorted(set(p.folder for p in PROCESSES)):
        count = len([p for p in PROCESSES if p.folder == folder])
        print(f"  - {folder}/ ({count} processes)")


if __name__ == "__main__":
    main()
