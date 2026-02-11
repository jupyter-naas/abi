"""
NEXUS ORM Models

SQLAlchemy 2.0 declarative models for all database tables.
These replace raw SQL strings throughout the codebase.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
    func, Boolean,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================
# Organizations
# ============================================

class OrganizationModel(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Branding
    logo_url = Column(Text, nullable=True)          # Square logo (icon, sidebar, compact)
    logo_rectangle_url = Column(Text, nullable=True) # Wide/horizontal logo (login page, headers)
    logo_emoji = Column(String, nullable=True)
    primary_color = Column(String, nullable=True, default="#22c55e")
    accent_color = Column(String, nullable=True)
    background_color = Column(String, nullable=True)
    font_family = Column(String, nullable=True)
    font_url = Column(Text, nullable=True)                  # CSS/Typekit URL to load custom font
    login_card_max_width = Column(String, nullable=True)    # e.g. "440px"
    login_card_padding = Column(String, nullable=True)      # e.g. "2.5rem 3rem 3rem"

    # Login page options
    login_card_color = Column(String, nullable=True)       # Card background color (e.g. #ffffff)
    login_text_color = Column(String, nullable=True)       # Text color on the card (e.g. #1a1a1a for dark)
    login_input_color = Column(String, nullable=True)      # Input background color (e.g. #B1B3B3)
    login_border_radius = Column(String, nullable=True)    # Border radius in px (e.g. "0" for sharp, "16" for rounded)
    login_bg_image_url = Column(Text, nullable=True)       # Background image URL for login page
    show_terms_footer = Column(Boolean, nullable=False, default=True)     # "By signing in, you agree to..."
    show_powered_by = Column(Boolean, nullable=False, default=True)       # "Powered by NEXUS"
    login_footer_text = Column(Text, nullable=True)                        # Custom footer line (e.g. "© 2026 Forvis Mazars - Confidentiel")
    secondary_logo_url = Column(Text, nullable=True)                      # Second logo (e.g. partner) for dual-logo layout
    show_logo_separator = Column(Boolean, nullable=False, default=False)  # Vertical bar between primary and secondary logo
    default_theme = Column(String, nullable=True, default=None)            # "light", "dark", or null (system)

    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    owner = relationship("UserModel", back_populates="organizations_owned", foreign_keys=[owner_id])
    members = relationship("OrganizationMemberModel", back_populates="organization", cascade="all, delete-orphan")
    domains = relationship("OrganizationDomainModel", back_populates="organization", cascade="all, delete-orphan")
    workspaces = relationship("WorkspaceModel", back_populates="organization")


# ============================================
# Organization Members
# ============================================

class OrganizationMemberModel(Base):
    __tablename__ = "organization_members"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member")  # owner, admin, member
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_user"),
    )

    # Relationships
    organization = relationship("OrganizationModel", back_populates="members")
    user = relationship("UserModel", back_populates="org_memberships")


# ============================================
# Organization Domains
# ============================================

class OrganizationDomainModel(Base):
    __tablename__ = "organization_domains"

    id = Column(String, primary_key=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String, nullable=False, unique=True, index=True)  # e.g. "login.company.com"
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
    hashed_password = Column(String, nullable=False)
    avatar = Column(String, nullable=True)
    company = Column(String, nullable=True)
    role = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    organizations_owned = relationship("OrganizationModel", back_populates="owner", foreign_keys="OrganizationModel.owner_id", cascade="all, delete-orphan")
    org_memberships = relationship("OrganizationMemberModel", back_populates="user", cascade="all, delete-orphan")
    workspaces_owned = relationship("WorkspaceModel", back_populates="owner", cascade="all, delete-orphan")
    memberships = relationship("WorkspaceMemberModel", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("ConversationModel", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetTokenModel", back_populates="user", cascade="all, delete-orphan")


# ============================================
# Password Reset Tokens
# ============================================

class PasswordResetTokenModel(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=False), nullable=False)
    used = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    # Relationships
    user = relationship("UserModel", back_populates="password_reset_tokens")


# ============================================
# Workspaces
# ============================================

class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Workspace-level theming (personal workspace branding)
    logo_url = Column(Text, nullable=True)             # URL to workspace logo image
    logo_emoji = Column(String, nullable=True)         # Emoji icon (fallback if no logo URL)
    primary_color = Column(String, nullable=True, default="#22c55e")  # Primary brand color (hex)
    accent_color = Column(String, nullable=True)       # Accent/secondary color (hex)
    background_color = Column(String, nullable=True)   # Custom background color (hex)
    sidebar_color = Column(String, nullable=True)      # Custom sidebar background color (hex)
    font_family = Column(String, nullable=True)        # Custom font family name
    
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    owner = relationship("UserModel", back_populates="workspaces_owned")
    organization = relationship("OrganizationModel", back_populates="workspaces")
    members = relationship("WorkspaceMemberModel", back_populates="workspace", cascade="all, delete-orphan")
    conversations = relationship("ConversationModel", back_populates="workspace", cascade="all, delete-orphan")
    graph_nodes = relationship("GraphNodeModel", back_populates="workspace", cascade="all, delete-orphan")
    graph_edges = relationship("GraphEdgeModel", back_populates="workspace", cascade="all, delete-orphan")
    secrets = relationship("SecretModel", back_populates="workspace", cascade="all, delete-orphan")
    abi_servers = relationship("ABIServerModel", back_populates="workspace", cascade="all, delete-orphan")
    inference_servers = relationship("InferenceServerModel", back_populates="workspace", cascade="all, delete-orphan")



# ============================================
# ABI Servers (External AI Engines per Workspace)
# ============================================

class ABIServerModel(Base):
    __tablename__ = "abi_servers"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    endpoint = Column(Text, nullable=False)
    api_key = Column(Text, nullable=True)  # Encrypted
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "endpoint", name="uq_workspace_endpoint"),
    )

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="abi_servers")


class InferenceServerModel(Base):
    """Generic inference server model (Ollama, vLLM, llama.cpp, custom, etc.)"""
    __tablename__ = "inference_servers"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
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
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member")  # owner, admin, member, viewer
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="members")
    user = relationship("UserModel", back_populates="memberships")


# ============================================
# Conversations
# ============================================

class ConversationModel(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
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
    messages = relationship("MessageModel", back_populates="conversation", cascade="all, delete-orphan", order_by="MessageModel.created_at")


# ============================================
# Messages
# ============================================

class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    agent = Column(String, nullable=True)
    metadata_ = Column("metadata", Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    # Relationships
    conversation = relationship("ConversationModel", back_populates="messages")


# ============================================
# Ontologies
# ============================================

class OntologyModel(Base):
    __tablename__ = "ontologies"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    schema_ = Column("schema", Text, nullable=False)  # JSON schema
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Graph Nodes
# ============================================

class GraphNodeModel(Base):
    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    label = Column(String, nullable=False)
    properties = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="graph_nodes")
    edges_as_source = relationship("GraphEdgeModel", foreign_keys="GraphEdgeModel.source_id", back_populates="source_node", cascade="all, delete-orphan")
    edges_as_target = relationship("GraphEdgeModel", foreign_keys="GraphEdgeModel.target_id", back_populates="target_node", cascade="all, delete-orphan")


# ============================================
# Graph Edges
# ============================================

class GraphEdgeModel(Base):
    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(String, ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, nullable=False)
    properties = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="graph_edges")
    source_node = relationship("GraphNodeModel", foreign_keys=[source_id], back_populates="edges_as_source")
    target_node = relationship("GraphNodeModel", foreign_keys=[target_id], back_populates="edges_as_target")


# ============================================
# API Keys
# ============================================

class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    key_hash = Column(String, nullable=False)
    key_prefix = Column(String, nullable=False)
    last_used_at = Column(String, nullable=True)
    expires_at = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)


# ============================================
# Provider Configurations
# ============================================

class ProviderConfigModel(Base):
    __tablename__ = "provider_configs"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
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

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    logo_url = Column(Text, nullable=True)  # URL to agent/provider logo
    system_prompt = Column(Text, nullable=True)
    provider_id = Column(String, ForeignKey("provider_configs.id", ondelete="SET NULL"), nullable=True)
    model_id = Column(String, nullable=True, index=True)  # Links to model registry
    provider = Column(String, nullable=True, index=True)  # Provider name (xai, openai, anthropic, etc.)
    is_default = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, nullable=False, default=False)  # Whether agent is available for chat
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)


# ============================================
# Secrets
# ============================================

class SecretModel(Base):
    __tablename__ = "secrets"

    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String, nullable=False)
    encrypted_value = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, nullable=False, default="other")
    created_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=False), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_workspace_key"),
    )

    # Relationships
    workspace = relationship("WorkspaceModel", back_populates="secrets")
