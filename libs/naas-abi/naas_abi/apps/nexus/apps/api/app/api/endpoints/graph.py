"""
Knowledge Graph API endpoints - Graph exploration and queries.
Async sessions with SQLAlchemy ORM.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import GraphNodeModel, GraphEdgeModel
from app.api.endpoints.auth import (
    User, get_current_user_required, require_workspace_access,
)

router = APIRouter(dependencies=[Depends(get_current_user_required)])


# ============ Pydantic Schemas ============

class GraphNode(BaseModel):
    id: str
    workspace_id: str
    type: str
    label: str
    properties: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphEdge(BaseModel):
    id: str
    workspace_id: str
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = {}
    created_at: datetime | None = None


class GraphNodeCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=500)
    properties: dict[str, Any] = {}


class GraphNodeUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=500)
    type: str | None = Field(None, min_length=1, max_length=100)
    properties: dict[str, Any] | None = None


class GraphEdgeCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    source_id: str = Field(..., min_length=1, max_length=100)
    target_id: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=100)
    properties: dict[str, Any] = {}


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=10_000)
    language: Literal["natural", "sparql"] = "natural"
    limit: int = Field(default=100, ge=1, le=5000)


class GraphQueryResult(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    query_explanation: str | None = None


# ============ Helpers ============

def _to_node(row: GraphNodeModel) -> GraphNode:
    return GraphNode(
        id=row.id, workspace_id=row.workspace_id, type=row.type, label=row.label,
        properties=json.loads(row.properties) if row.properties else {},
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_edge(row: GraphEdgeModel) -> GraphEdge:
    return GraphEdge(
        id=row.id, workspace_id=row.workspace_id, source_id=row.source_id,
        target_id=row.target_id, type=row.type,
        properties=json.loads(row.properties) if row.properties else {},
        created_at=row.created_at,
    )


# ============ Endpoints ============

@router.get("/workspaces/{workspace_id}")
async def get_workspace_graph(
    workspace_id: str,
    node_type: str | None = None,
    limit: int = Query(default=1000, le=5000),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphData:
    """Get all nodes and edges for a workspace."""
    await require_workspace_access(current_user.id, workspace_id)

    stmt = select(GraphNodeModel).where(GraphNodeModel.workspace_id == workspace_id)
    if node_type:
        stmt = stmt.where(GraphNodeModel.type == node_type)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    nodes = [_to_node(r) for r in result.scalars().all()]

    node_ids = [n.id for n in nodes]
    edges = []
    if node_ids:
        edge_result = await db.execute(
            select(GraphEdgeModel).where(
                GraphEdgeModel.workspace_id == workspace_id,
                or_(
                    GraphEdgeModel.source_id.in_(node_ids),
                    GraphEdgeModel.target_id.in_(node_ids),
                )
            )
        )
        edges = [_to_edge(r) for r in edge_result.scalars().all()]

    return GraphData(nodes=nodes, edges=edges)


@router.get("/nodes")
async def list_nodes(
    workspace_id: str,
    type: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[GraphNode]:
    """List nodes, optionally filtered by type."""
    await require_workspace_access(current_user.id, workspace_id)
    stmt = select(GraphNodeModel).where(GraphNodeModel.workspace_id == workspace_id)
    if type:
        stmt = stmt.where(GraphNodeModel.type == type)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [_to_node(r) for r in result.scalars().all()]


@router.post("/nodes")
async def create_node(
    node: GraphNodeCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphNode:
    """Create a new node."""
    await require_workspace_access(current_user.id, node.workspace_id)
    node_id = f"node-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    row = GraphNodeModel(
        id=node_id, workspace_id=node.workspace_id, type=node.type, label=node.label,
        properties=json.dumps(node.properties), created_at=now, updated_at=now,
    )
    db.add(row)
    await db.flush()
    return _to_node(row)


@router.get("/nodes/{node_id}")
async def get_node(
    node_id: str,
    db: AsyncSession = Depends(get_db),
) -> GraphNode:
    """Get a node by ID."""
    result = await db.execute(select(GraphNodeModel).where(GraphNodeModel.id == node_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Node not found")
    return _to_node(row)


@router.put("/nodes/{node_id}")
async def update_node(
    node_id: str,
    updates: GraphNodeUpdate,
    db: AsyncSession = Depends(get_db),
) -> GraphNode:
    """Update a node."""
    result = await db.execute(select(GraphNodeModel).where(GraphNodeModel.id == node_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Node not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row.updated_at = now
    if updates.label is not None:
        row.label = updates.label
    if updates.type is not None:
        row.type = updates.type
    if updates.properties is not None:
        row.properties = json.dumps(updates.properties)

    await db.flush()
    return _to_node(row)


@router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a node and its connected edges."""
    result = await db.execute(select(GraphNodeModel).where(GraphNodeModel.id == node_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Node not found")

    # Count edges
    edge_count = (await db.execute(
        select(func.count()).select_from(GraphEdgeModel).where(
            or_(GraphEdgeModel.source_id == node_id, GraphEdgeModel.target_id == node_id)
        )
    )).scalar() or 0

    # Delete edges first
    await db.execute(
        delete(GraphEdgeModel).where(
            or_(GraphEdgeModel.source_id == node_id, GraphEdgeModel.target_id == node_id)
        )
    )
    await db.delete(row)

    return {"status": "deleted", "edges_deleted": edge_count}


@router.get("/edges")
async def list_edges(
    workspace_id: str,
    type: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[GraphEdge]:
    """List edges, optionally filtered by type."""
    await require_workspace_access(current_user.id, workspace_id)
    stmt = select(GraphEdgeModel).where(GraphEdgeModel.workspace_id == workspace_id)
    if type:
        stmt = stmt.where(GraphEdgeModel.type == type)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [_to_edge(r) for r in result.scalars().all()]


@router.post("/edges")
async def create_edge(
    edge: GraphEdgeCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphEdge:
    """Create a new edge between nodes."""
    await require_workspace_access(current_user.id, edge.workspace_id)

    # Verify source and target exist
    for nid, label in [(edge.source_id, "Source"), (edge.target_id, "Target")]:
        result = await db.execute(select(GraphNodeModel.id).where(GraphNodeModel.id == nid))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"{label} node not found")

    edge_id = f"edge-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    row = GraphEdgeModel(
        id=edge_id, workspace_id=edge.workspace_id, source_id=edge.source_id,
        target_id=edge.target_id, type=edge.type, properties=json.dumps(edge.properties),
        created_at=now,
    )
    db.add(row)
    await db.flush()
    return _to_edge(row)


@router.get("/edges/{edge_id}")
async def get_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
) -> GraphEdge:
    """Get an edge by ID."""
    result = await db.execute(select(GraphEdgeModel).where(GraphEdgeModel.id == edge_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Edge not found")
    return _to_edge(row)


@router.delete("/edges/{edge_id}")
async def delete_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete an edge."""
    result = await db.execute(select(GraphEdgeModel).where(GraphEdgeModel.id == edge_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Edge not found")
    await db.delete(row)
    return {"status": "deleted"}


@router.post("/query")
async def query_graph(
    request: GraphQuery,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> GraphQueryResult:
    """Query the knowledge graph."""
    await require_workspace_access(current_user.id, workspace_id)

    result = await db.execute(
        select(GraphNodeModel).where(
            GraphNodeModel.workspace_id == workspace_id,
            or_(
                GraphNodeModel.label.ilike(f"%{request.query}%"),
                GraphNodeModel.type.ilike(f"%{request.query}%"),
            )
        ).limit(request.limit)
    )
    nodes = [_to_node(r) for r in result.scalars().all()]

    node_ids = [n.id for n in nodes]
    edges = []
    if node_ids:
        edge_result = await db.execute(
            select(GraphEdgeModel).where(
                GraphEdgeModel.workspace_id == workspace_id,
                GraphEdgeModel.source_id.in_(node_ids),
                GraphEdgeModel.target_id.in_(node_ids),
            )
        )
        edges = [_to_edge(r) for r in edge_result.scalars().all()]

    return GraphQueryResult(
        nodes=nodes, edges=edges,
        query_explanation=f"Found {len(nodes)} nodes matching '{request.query}'",
    )


@router.get("/statistics/{workspace_id}")
async def get_graph_statistics(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get statistics for a workspace's graph."""
    await require_workspace_access(current_user.id, workspace_id)

    total_nodes = (await db.execute(
        select(func.count()).select_from(GraphNodeModel).where(GraphNodeModel.workspace_id == workspace_id)
    )).scalar() or 0

    total_edges = (await db.execute(
        select(func.count()).select_from(GraphEdgeModel).where(GraphEdgeModel.workspace_id == workspace_id)
    )).scalar() or 0

    # Nodes by type
    type_result = await db.execute(
        select(GraphNodeModel.type, func.count().label("count"))
        .where(GraphNodeModel.workspace_id == workspace_id)
        .group_by(GraphNodeModel.type)
    )
    nodes_by_type = {row.type: row.count for row in type_result}

    # Edges by type
    edge_type_result = await db.execute(
        select(GraphEdgeModel.type, func.count().label("count"))
        .where(GraphEdgeModel.workspace_id == workspace_id)
        .group_by(GraphEdgeModel.type)
    )
    edges_by_type = {row.type: row.count for row in edge_type_result}

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "nodes_by_type": nodes_by_type,
        "edges_by_type": edges_by_type,
        "avg_degree": (2 * total_edges / total_nodes) if total_nodes > 0 else 0,
    }
