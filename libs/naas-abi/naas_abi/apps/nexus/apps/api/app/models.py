"""
NEXUS ORM Models

SQLAlchemy 2.0 declarative models for all database tables.
These replace raw SQL strings throughout the codebase.
"""

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ============================================
# Organizations
# ============================================


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Branding
    logo_url = Column(Text, nullable=True)  # Square logo (icon, sidebar, compact)
    logo_rectangle_url = Column(Text, nullable=True)  # Wide/horizontal logo (login page, headers)
    logo_emoji = Column(String, nullable=True)
    primary_color = Column(String, nullable=True, default="#22c55e")
    accent_color = Column(String, nullable=True)
    background_color = Column(String, nullable=True)
    font_family = Column(String, nullable=True)
    font_url = Column(Text, nullable=True)  # CSS/Typekit URL to load custom font
    login_card_max_width = Column(String, nullable=True)  # e.g. "440px"
    login_card_padding = Column(String, nullable=True)  # e.g. "2.5rem 3rem 3rem"

    # Login page options
    login_card_color = Column(String, nullable=True)  # Card background color (e.g. #ffffff)
    login_text_color = Column(
        String, nullable=True
    )  # Text color on the card (e.g. #1a1a1a for dark)
    login_input_color = Column(String, nullable=True)  # Input background color (e.g. #B1B3B3)
    login_border_radius = Column(
        String, nullable=True
    )  # Border radius in px (e.g. "0" for sharp, "16" for rounded)
    login_bg_image_url = Column(Text, nullable=True)  # Background image URL for login page
    show_terms_footer = Column(
        Boolean, nullable=False, default=True
    )  # "By signing in, you agree to..."
    show_powered_by = Column(Boolean, nullable=False, default=True)  # "Powered by NEXUS"
    login_footer_text = Column(
        Text, nullable=True
    )  # Custom footer line (e.g. "© 2026 Forvis Mazars - Confidentiel")
    secondary_logo_url = Column(
        Text, nullable=True
    )  # Second logo (e.g. partner) for dual-logo layout
    show_logo_separator = Column(
        Boolean, nullable=False, default=False
    )  # Vertical bar between primary and secondary logo
    default_theme = Column(String, nullable=True, default=None)  # "light", "dark", or null (system)

    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    owner = relationship("UserModel", back_populates="organizations_owned", foreign_keys=[owner_id])
    members = relationship(
        "OrganizationMemberModel", back_populates="organization", cascade="all, delete-orphan"
    )
    domains = relationship(
        "OrganizationDomainModel", back_populates="organization", cascade="all, delete-orphan"
    )
    workspaces = relationship("WorkspaceModel", back_populates="organization")


# ============================================
# Organization Members
# ============================================


class OrganizationMemberModel(Base):
    __tablename__ = "organization_members"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member")  # owner, admin, member
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    # Profile in this organization, set by its admins. NULL falls back to the
    # account value on users.* (see organizations postgres adapter).
    name = Column(String(200), nullable=True)
    avatar = Column(String, nullable=True)
    # Column "organization" (was company, migration 0055). The attribute name differs
    # because `organization` is the relationship to the OrganizationModel row.
    organization_name = Column("organization", String(200), nullable=True)
    service_line = Column(String(200), nullable=True)
    country = Column(String(100), nullable=True)
    interest = Column(String(1000), nullable=True)
    job_title = Column(String(100), nullable=True)
    bio = Column(String(2000), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_organization_user"),)

    # Relationships
    organization = relationship("OrganizationModel", back_populates="members")
    user = relationship("UserModel", back_populates="org_memberships")


# ============================================
# Organization Domains
# ============================================


class OrganizationDomainModel(Base):
    __tablename__ = "organization_domains"

    id = Column(String, primary_key=True)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain = Column(String, nullable=False, unique=True, index=True)  # e.g. "login.company.com"
    # The identity provider (``identity.providers[].name``) a login with an email
    # of this domain goes to; None: the default provider.
    provider = Column(String(64), nullable=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String, nullable=True)  # Token for DNS verification
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    verified_at = Column(DateTime(timezone=False), nullable=True)

    # Relationships
    organization = relationship("OrganizationModel", back_populates="domains")


# ============================================
# Users
# ============================================


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    avatar = Column(String, nullable=True)
    organization = Column(String, nullable=True)  # was company (migration 0053)
    job_title = Column(String, nullable=True)  # was role (migration 0054)
    bio = Column(String, nullable=True)
    is_superadmin = Column(Boolean, nullable=False, default=False, server_default="false")
    # A user signed in through an identity provider: one row per (issuer, sub),
    # whose id is its IAM principal id. The rows of the old built-in login keep
    # their id (and every row that points at it) and get their identity at the
    # first sign-in through the built-in provider (``services/oidc``).
    principal_id = Column(String(255), nullable=True, unique=True)
    idp_provider = Column(String(64), nullable=True)
    idp_issuer = Column(String(1024), nullable=True)
    idp_subject = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("idp_issuer", "idp_subject", name="uq_users_idp_identity"),)

    # Relationships
    organizations_owned = relationship(
        "OrganizationModel",
        back_populates="owner",
        foreign_keys="OrganizationModel.owner_id",
        cascade="all, delete-orphan",
    )
    org_memberships = relationship(
        "OrganizationMemberModel", back_populates="user", cascade="all, delete-orphan"
    )
    workspaces_owned = relationship(
        "WorkspaceModel", back_populates="owner", cascade="all, delete-orphan"
    )
    memberships = relationship(
        "WorkspaceMemberModel", back_populates="user", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "ConversationModel", back_populates="user", cascade="all, delete-orphan"
    )


# ============================================
# Sign-in through identity providers
# ============================================


class OidcLoginRequestModel(Base):
    """A sign-in in flight: single use, ten minutes at most."""

    __tablename__ = "oidc_login_requests"

    state_hash = Column(String(64), primary_key=True)
    provider = Column(String(64), nullable=False)
    nonce = Column(String(128), nullable=False)
    code_verifier = Column(String(128), nullable=False)
    binding_hash = Column(String(64), nullable=False)
    next_path = Column(String(2048), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    expires_at = Column(DateTime(timezone=False), nullable=False)


class AuthSessionModel(Base):
    """A browser session the API holds; its id is the SHA-256 of the cookie's secret."""

    __tablename__ = "auth_sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(
        String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    principal_id = Column(String(255), nullable=False)
    provider = Column(String(64), nullable=False)
    group_ids = Column(Text, nullable=False, default="[]")
    refresh_token_enc = Column(Text, nullable=True)
    id_token_enc = Column(Text, nullable=True)
    refresh_at = Column(DateTime(timezone=False), nullable=False)
    expires_at = Column(DateTime(timezone=False), nullable=False)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime(timezone=False), nullable=True)
    revoked_at = Column(DateTime(timezone=False), nullable=True)
    user_agent = Column(String(512), nullable=True)


# ============================================
# Workspaces
# ============================================


class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    owner_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Workspace-level theming (personal workspace branding)
    logo_url = Column(Text, nullable=True)  # URL to workspace logo image
    logo_emoji = Column(String, nullable=True)  # Emoji icon (fallback if no logo URL)
    primary_color = Column(String, nullable=True, default="#22c55e")  # Primary brand color (hex)
    accent_color = Column(String, nullable=True)  # Accent/secondary color (hex)
    background_color = Column(String, nullable=True)  # Custom background color (hex)
    background_image_url = Column(Text, nullable=True)  # Desktop wallpaper URL
    sidebar_color = Column(String, nullable=True)  # Custom sidebar background color (hex)
    font_family = Column(String, nullable=True)  # Custom font family name
    description = Column(Text, nullable=True)  # Settings → General
    workspace_group = Column(String(100), nullable=True)  # workspace lists ("Others" if empty)
    # JSON {feature: bool} saved in Organization Settings; NULL = config overrides.
    feature_overrides = Column(Text, nullable=True)
    # JSON catalog chosen at workspace create (agents, apps, ontologies, …).
    catalog_seed = Column(Text, nullable=True)

    # Drive-scope feature flags
    platform_drive_enabled = Column(Boolean, nullable=False, default=False)
    system_drive_enabled = Column(Boolean, nullable=False, default=False)

    # Default git repo (owner/name) cloned for new coding workspaces here.
    coding_default_repo_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    owner = relationship("UserModel", back_populates="workspaces_owned")
    organization = relationship("OrganizationModel", back_populates="workspaces")
    members = relationship(
        "WorkspaceMemberModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "ConversationModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    graph_nodes = relationship(
        "GraphNodeModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    graph_edges = relationship(
        "GraphEdgeModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    secrets = relationship("SecretModel", back_populates="workspace", cascade="all, delete-orphan")
    abi_servers = relationship(
        "ABIServerModel", back_populates="workspace", cascade="all, delete-orphan"
    )
    inference_servers = relationship(
        "InferenceServerModel", back_populates="workspace", cascade="all, delete-orphan"
    )


# ============================================
# Coding Environments (per-repo binding for Coder workspaces)
# ============================================


class CodingEnvironmentModel(Base):
    """Binds a Coder workspace to the repo (or Slides slug) it was cloned from.

    Coder owns the workspace lifecycle; this row records which repo a workspace
    belongs to so the workspaces list can be scoped per-repo. For Slides,
    ``label`` is ``slides/<slug>`` and sidecar credentials let the Nexus Abi
    pane bind workspace filesystem tools (Continue-parity).
    """

    __tablename__ = "coding_environments"

    id = Column(String, primary_key=True)  # Coder workspace UUID
    workspace_id = Column(String, nullable=False, index=True)  # Nexus workspace id
    user_id = Column(String, nullable=False, index=True)  # Nexus user id (provisioner)
    repo_id = Column(String, nullable=True)  # "owner/name" of the cloned repo
    label = Column(String, nullable=True)  # e.g. slides/<slug> for Slides runtimes
    sidecar_base = Column(String, nullable=True)  # http://coder-<user>-slides-<slug>:8378
    sidecar_secret = Column(String, nullable=True)  # bearer for abi_sidecar
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


# ============================================
# ABI Servers (External AI Engines per Workspace)
# ============================================


class ABIServerModel(Base):
    __tablename__ = "abi_servers"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    endpoint = Column(Text, nullable=False)
    api_key = Column(Text, nullable=True)  # Encrypted
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("workspace_id", "endpoint", name="uq_workspace_endpoint"),)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="abi_servers")


class InferenceServerModel(Base):
    """Generic inference server model (Ollama, vLLM, llama.cpp, custom, etc.)"""

    __tablename__ = "inference_servers"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'ollama', 'abi', 'vllm', 'llamacpp', 'custom'
    endpoint = Column(Text, nullable=False)  # Base URL
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    api_key = Column(Text, nullable=True)  # Optional auth
    health_path = Column(String, nullable=True)  # Health check endpoint path
    models_path = Column(String, nullable=True)  # Models list endpoint path
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="inference_servers")


# ============================================
# Workspace Members
# ============================================


class WorkspaceMemberModel(Base):
    __tablename__ = "workspace_members"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member")  # owner, admin, member, viewer
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="members")
    user = relationship("UserModel", back_populates="memberships")


# ============================================
# Conversations
# ============================================


class ConversationModel(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False, default="New Conversation")
    agent = Column(String, nullable=False, default="aia")
    pinned = Column(Boolean, nullable=False, default=False)
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="conversations")
    user = relationship("UserModel", back_populates="conversations")
    messages = relationship(
        "MessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageModel.created_at",
    )


# ============================================
# Messages
# ============================================


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    agent = Column(String, nullable=True)
    metadata_ = Column("metadata", Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    # Relationships
    conversation = relationship("ConversationModel", back_populates="messages")


class ChatIngestionJobModel(Base):
    __tablename__ = "chat_ingestion_jobs"

    id = Column(String, primary_key=True)
    conversation_id = Column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String, nullable=False, default="my_drive")
    source_path = Column(Text, nullable=False)
    embedding_model = Column(String, nullable=False, default="hash-v1")
    embedding_dimension = Column(Integer, nullable=False, default=256)
    status = Column(String, nullable=False, default="queued", index=True)
    progress = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, nullable=True)
    file_sha256 = Column(String, nullable=True)
    collection_name = Column(String, nullable=True)
    chunks_count = Column(Integer, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)
    started_at = Column(DateTime(timezone=False), nullable=True)
    finished_at = Column(DateTime(timezone=False), nullable=True)


# ============================================
# Ontologies
# ============================================


class OntologyModel(Base):
    __tablename__ = "ontologies"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    schema_ = Column("schema", Text, nullable=False)  # JSON schema
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class OntologyIconModel(Base):
    __tablename__ = "ontology_icons"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    target_key = Column(String(64), primary_key=True)
    resource_kind = Column(String(24), nullable=False)
    resource_id = Column(Text, nullable=False)
    icon_name = Column(Text, nullable=False)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Graph Nodes
# ============================================


class GraphNodeModel(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(String, nullable=False, index=True)
    label = Column(String, nullable=False)
    properties = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="graph_nodes")
    edges_as_source = relationship(
        "GraphEdgeModel",
        foreign_keys="GraphEdgeModel.source_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    edges_as_target = relationship(
        "GraphEdgeModel",
        foreign_keys="GraphEdgeModel.target_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )


# ============================================
# Graph Edges
# ============================================


class GraphViewModel(Base):
    __tablename__ = "graph_views"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)  # free-text "what does this view answer?"
    view_type = Column(String(100), nullable=False, default="network")
    kind = Column(String(50), nullable=False, default="network")
    visibility = Column(String(20), nullable=False, default="workspace")
    creator_id = Column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    graph_id = Column(String, nullable=False)
    graph_uri = Column(Text, nullable=False)
    state = Column(Text, nullable=False)
    path = Column(String(1024), nullable=False, default="")  # folder path; "" = root
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    workspace = relationship("WorkspaceModel")
    creator = relationship("UserModel")


class GraphEdgeModel(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id = Column(
        String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id = Column(
        String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(String, nullable=False)
    properties = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="graph_edges")
    source_node = relationship(
        "GraphNodeModel", foreign_keys=[source_id], back_populates="edges_as_source"
    )
    target_node = relationship(
        "GraphNodeModel", foreign_keys=[target_id], back_populates="edges_as_target"
    )


# ============================================
# Provider Configurations
# ============================================


class ProviderConfigModel(Base):
    __tablename__ = "provider_configs"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    model = Column(String, nullable=False)
    enabled = Column(Integer, nullable=False, default=0)
    endpoint = Column(String, nullable=True)
    config = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Agent Configurations
# ============================================


class AgentConfigModel(Base):
    __tablename__ = "agent_configs"
    # Partial unique index uq_agent_configs_workspace_class_name is created in
    # migration 0041 (workspace_id, class_name) WHERE class_name IS NOT NULL.
    # Declared only in SQL because SQLAlchemy cannot express that partial index
    # portably across SQLite/Postgres here.

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String, nullable=False)
    class_name = Column(
        String, nullable=True, index=True
    )  # Fully-qualified in-process ABI class path
    module_path = Column(
        String, nullable=True, index=True
    )  # Python module path of the agent class (e.g. naas_abi_marketplace.applications.foo)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    logo_url = Column(Text, nullable=True)  # URL to agent/provider logo
    system_prompt = Column(Text, nullable=True)
    provider_id = Column(
        String, ForeignKey("provider_configs.id", ondelete="SET NULL"), nullable=True
    )
    model_id = Column(String, nullable=True, index=True)  # Links to model registry
    provider = Column(
        String, nullable=True, index=True
    )  # Provider name (xai, openai, anthropic, etc.)
    is_default = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, nullable=False, default=False)  # Whether agent is available for chat
    # A user's explicit toggle; sync keeps it over the workspace roster. NULL = follow the roster.
    enabled_override = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Skills (user-created reusable prompt skills)
# ============================================


class SkillModel(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized from the workspace at creation time so organization-scoped
    # skills can be listed across all workspaces of the org with one filter.
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )  # Creator
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)  # Chat command: /<slug>
    description = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)  # Reusable prompt applied by the current agent
    scope = Column(String, nullable=False, default="user")  # user | workspace | organization
    enabled = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=False), nullable=True)  # Drives "latest used" ordering
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Organization role -> feature overlays
# ============================================


class OrganizationRoleFeaturesModel(Base):
    """Durable per-organization role_baseline overlay.

    ``role_baseline`` is a JSON object mapping role name to feature keys,
    e.g. ``{"owner": ["chat", "files"], "admin": [...], ...}``.
    """

    __tablename__ = "organization_role_features"

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_baseline = Column(Text, nullable=False)  # JSON object
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# App Configurations (per-workspace enable state)
# ============================================


class AppConfigModel(Base):
    __tablename__ = "app_configs"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Marketplace app identifier: "<module_path>:<app_name>" (e.g.
    # "naas_abi_marketplace.applications.openrouter:dashboard").
    app_id = Column(String(512), nullable=False, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "app_id", name="uq_app_configs_workspace_app"),
    )


# ============================================
# Secrets
# ============================================


class SecretModel(Base):
    __tablename__ = "secrets"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key = Column(String, nullable=False)
    encrypted_value = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, nullable=False, default="other")
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (UniqueConstraint("workspace_id", "key", name="uq_workspace_key"),)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="secrets")


# ============================================
# Model Catalog (marketplace AI model display properties)
# ============================================


class ModelCatalogRecordModel(Base):
    """Persistent store for a marketplace AI model's display properties.

    Mirrors a model discovered statically from
    ``naas_abi_marketplace.ai.*/models/*.py``. The effective columns
    (``name``..``context_window``) are what the API serves; ``source_*`` hold
    the last value seen in the Python source so a code change can be detected;
    ``overridden_fields`` is a JSON array of property names a user edited in the
    frontend — those keep their value across source changes (a warning is
    logged instead of overwriting).
    """

    __tablename__ = "model_catalog"

    canonical_id = Column(String, primary_key=True)
    model_id = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    provider_id = Column(String, nullable=False, index=True)
    module_path = Column(String, nullable=False)

    name = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    image = Column(Text, nullable=True)
    context_window = Column(Integer, nullable=True)

    source_name = Column(Text, nullable=True)
    source_description = Column(Text, nullable=True)
    source_image = Column(Text, nullable=True)
    source_context_window = Column(Integer, nullable=True)

    overridden_fields = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class WorkspaceResourcePolicyModel(Base):
    """Persisted workspace assignments; configuration is used only on first access."""

    __tablename__ = "workspace_resource_policies"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    resource_kind = Column(String(24), primary_key=True)
    policy = Column(Text, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


class SearchTopicModel(Base):
    """A workspace's search topic: an override of a built-in one, or a custom topic."""

    __tablename__ = "search_topics"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    topic_id = Column(String(48), primary_key=True)
    definition = Column(Text, nullable=False)  # JSON SearchTopic
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class SearchSettingsModel(Base):
    """A workspace's search settings: which feature and web-engine scopes are switched off."""

    __tablename__ = "search_settings"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    settings = Column(Text, nullable=False)  # JSON {"disabled_scopes": [...]}
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class MapsLayoutModel(Base):
    """A workspace's custom Maps layout: a SPARQL pin layer (JSON definition)."""

    __tablename__ = "maps_layouts"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    layout_id = Column(String(48), primary_key=True)
    definition = Column(Text, nullable=False)  # JSON MapsLayout
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class MapsBasemapModel(Base):
    """A workspace's Maps basemap: JSON definition plus its preview image."""

    __tablename__ = "maps_basemaps"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    basemap_id = Column(String(48), primary_key=True)
    definition = Column(Text, nullable=False)  # JSON MapsBasemap (no preview fields)
    preview = Column(LargeBinary, nullable=True)
    preview_content_type = Column(String(32), nullable=True)
    preview_version = Column(Integer, nullable=False, default=0)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class MapsFeedLayerModel(Base):
    """A workspace's map layer: a view on one of its feeds (JSON definition)."""

    __tablename__ = "maps_feed_layers"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    layer_id = Column(String(48), primary_key=True)
    feed_id = Column(String(48), nullable=False)
    definition = Column(Text, nullable=False)  # JSON MapsFeedLayer
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class MapsGrantModel(Base):
    """Which workspaces may use a Maps layer or basemap (deployment or custom item)."""

    __tablename__ = "maps_grants"

    kind = Column(String(16), primary_key=True)  # layout | basemap
    item_id = Column(String(48), primary_key=True)
    owner_workspace_id = Column(String, primary_key=True, default="")  # "" = deployment
    workspace_ids = Column(Text, nullable=True)  # JSON list; NULL = every workspace
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


class MapsSettingsModel(Base):
    """A workspace's Maps settings: hidden layers/basemaps, layer colors, applied seeds."""

    __tablename__ = "maps_settings"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    settings = Column(Text, nullable=False)  # JSON MapsWorkspaceSettings
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Invitations
# ============================================


class InvitationModel(Base):
    """An email invited to an organization and/or a workspace through one identity
    provider. IAM holds the roles as pending grants (``grant_ids``) until the
    person signs in."""

    __tablename__ = "invitations"

    id = Column(String, primary_key=True)
    email = Column(String(320), nullable=False)
    provider = Column(String(64), nullable=False)
    organization_id = Column(
        String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    org_role = Column(String(16), nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True)
    workspace_role = Column(String(16), nullable=True)
    invited_by = Column(String, nullable=True)
    grant_ids = Column(Text, nullable=False, default="[]")  # JSON list of IAM pending grant ids
    status = Column(String(16), nullable=False, default="pending")  # pending, accepted, revoked
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)
    accepted_at = Column(DateTime(timezone=False), nullable=True)
    accepted_user_id = Column(String, nullable=True)
    # JSON object: the member profile set at invitation (see ``invites.port.PROFILE_FIELDS``).
    profile = Column(Text, nullable=True)


# ============================================
# Workflow runs started from a workspace
# ============================================


class WorkflowRunOwnerModel(Base):
    """Who started a workflow or pipeline run, and in which workspace: job runs
    carry no owner of their own (``services/workflows``)."""

    __tablename__ = "workflow_run_owners"

    module_id = Column(String(255), primary_key=True)
    run_id = Column(String(255), primary_key=True)
    workflow = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


class WorkflowVisibilityModel(Base):
    """A workflow or pipeline a workspace's admins turned on or off for everyone
    in it (``services/workflows``, ``services/visibility``); none recorded: on."""

    __tablename__ = "workflow_visibility"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    type = Column(String(32), primary_key=True)
    module_id = Column(String(255), primary_key=True)
    name = Column(String(255), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Tasks
# ============================================


class TaskIterationModel(Base):
    """A run of whole weeks of a workspace's tasks, keyed by its first day."""

    __tablename__ = "task_iterations"
    __table_args__ = (UniqueConstraint("workspace_id", "start_date"),)

    id = Column(String(48), primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    # Last day, inclusive; NULL for iterations made before settings (one week).
    end_date = Column(Date, nullable=True)
    goal = Column(String(200), nullable=False, default="")
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


class TasksSettingsModel(Base):
    """A workspace's tasks configuration (iterations, stages, priorities, labels)."""

    __tablename__ = "task_settings"

    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    data = Column(Text, nullable=False, default="{}")  # JSON
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


class TaskModel(Base):
    """A workspace task. No iteration means it sits in the backlog."""

    __tablename__ = "tasks"

    id = Column(String(48), primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    iteration_id = Column(
        String(48), ForeignKey("task_iterations.id", ondelete="SET NULL"), nullable=True
    )
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False, default="")
    stage = Column(String(32), nullable=False, default="inbox")
    priority = Column(String(16), nullable=True)
    due_date = Column(Date, nullable=True)
    labels = Column(Text, nullable=False, default="[]")  # JSON list
    # https://github.com/<owner>/<repo>/issues/<number>, or empty.
    github_issue_url = Column(String(500), nullable=False, default="")
    assignee_ids = Column(Text, nullable=False, default="[]")  # JSON list
    archived_at = Column(DateTime(timezone=False), nullable=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


class TaskCommentModel(Base):
    __tablename__ = "task_comments"

    id = Column(String(48), primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(48), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # The comment this one replies to; replies go with it.
    parent_id = Column(
        String(48), ForeignKey("task_comments.id", ondelete="CASCADE"), nullable=True
    )
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


class TaskActivityModel(Base):
    """A task event: a change, a comment, its deletion. Outlives the task (feed history)."""

    __tablename__ = "task_activity"

    id = Column(String(48), primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    # No foreign key: a deleted task's events stay in the workspace feed.
    task_id = Column(String(48), nullable=False)
    # The task's title when the event happened.
    task_title = Column(String(300), nullable=False, default="")
    actor_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    field = Column(String(32), nullable=False)
    old_value = Column(Text, nullable=True)  # JSON
    new_value = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
