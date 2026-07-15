from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataLineageEdge, DataLineageNode


def get_or_create_node(
    session: Session,
    node_type: str,
    node_reference: str,
    title: str,
    system_name: str = "LSTA",
    metadata_json: dict[str, Any] | None = None,
) -> DataLineageNode:
    node = session.scalar(
        select(DataLineageNode).where(
            DataLineageNode.node_type == node_type, DataLineageNode.node_reference == node_reference
        )
    )
    if not node:
        node = DataLineageNode(
            node_type=node_type,
            node_reference=node_reference,
            title=title,
            system_name=system_name,
            metadata_json=metadata_json or {},
        )
        session.add(node)
        session.flush()
    return node


def _reachable(session: Session, start, goal, max_depth=10) -> bool:
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for target in session.scalars(
            select(DataLineageEdge.target_node_id).where(DataLineageEdge.source_node_id == current)
        ):
            if target == goal:
                return True
            if target not in seen:
                seen.add(target)
                queue.append((target, depth + 1))
    return False


def create_lineage_edge(
    session: Session,
    source: DataLineageNode,
    target: DataLineageNode,
    transformation_type: str,
    process_name: str,
    **data: Any,
) -> DataLineageEdge:
    existing = session.scalar(
        select(DataLineageEdge).where(
            DataLineageEdge.source_node_id == source.id,
            DataLineageEdge.target_node_id == target.id,
            DataLineageEdge.transformation_type == transformation_type,
        )
    )
    if existing:
        return existing
    if source.id == target.id or _reachable(session, target.id, source.id):
        raise ValueError("circular lineage is not allowed")
    edge = DataLineageEdge(
        source_node_id=source.id,
        target_node_id=target.id,
        transformation_type=transformation_type,
        process_name=process_name,
        **data,
    )
    session.add(edge)
    session.flush()
    return edge


def _trace(session: Session, node_id, direction: str, depth: int = 3) -> dict[str, Any]:
    depth = max(0, min(depth, 10))
    nodes = {node_id}
    edges = []
    frontier = {node_id}
    for _ in range(depth):
        col = DataLineageEdge.target_node_id if direction == "upstream" else DataLineageEdge.source_node_id
        rows = list(session.scalars(select(DataLineageEdge).where(col.in_(frontier))).unique())
        new = set()
        for edge in rows:
            edges.append(edge)
            new.add(edge.source_node_id if direction == "upstream" else edge.target_node_id)
        frontier = new - nodes
        nodes |= new
        if not frontier or len(nodes) >= 250:
            break
    return {
        "nodes": list(session.scalars(select(DataLineageNode).where(DataLineageNode.id.in_(nodes))))[:250],
        "edges": edges[:250],
    }


def trace_upstream(session: Session, node_id, depth: int = 3):
    return _trace(session, node_id, "upstream", depth)


def trace_downstream(session: Session, node_id, depth: int = 3):
    return _trace(session, node_id, "downstream", depth)


def get_full_lineage_graph(session: Session, node_id, depth: int = 3):
    up = trace_upstream(session, node_id, depth)
    down = trace_downstream(session, node_id, depth)
    nodes = {n.id: n for n in up["nodes"] + down["nodes"]}
    edges = {e.id: e for e in up["edges"] + down["edges"]}
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


def validate_lineage_integrity(session: Session) -> dict[str, int]:
    return {
        "orphan_nodes": int(
            session.scalar(
                select(DataLineageNode)
                .where(
                    ~DataLineageNode.id.in_(select(DataLineageEdge.source_node_id)),
                    ~DataLineageNode.id.in_(select(DataLineageEdge.target_node_id)),
                )
                .with_only_columns(__import__("sqlalchemy").func.count())
            )
            or 0
        )
    }


def link_source_to_import_batch(session, source_ref, batch_ref):
    return create_lineage_edge(
        session,
        get_or_create_node(session, "source_file", source_ref, source_ref),
        get_or_create_node(session, "import_batch", batch_ref, batch_ref),
        "imported_from",
        "KML importer",
    )


def link_import_batch_to_staging(session, batch_ref, feature_ref):
    return create_lineage_edge(
        session,
        get_or_create_node(session, "import_batch", batch_ref, batch_ref),
        get_or_create_node(session, "staging_feature", feature_ref, feature_ref),
        "parsed_into",
        "KML importer",
    )


def link_staging_to_national_site(session, feature_ref, site_ref):
    return create_lineage_edge(
        session,
        get_or_create_node(session, "staging_feature", feature_ref, feature_ref),
        get_or_create_node(session, "national_site", site_ref, site_ref),
        "promoted_to",
        "Promotion service",
    )


def link_site_to_geometry(session, site_ref, geometry_ref):
    return create_lineage_edge(
        session,
        get_or_create_node(session, "national_site", site_ref, site_ref),
        get_or_create_node(session, "site_geometry", geometry_ref, geometry_ref),
        "linked_to",
        "Registry service",
    )


def _link_site_asset(session, site_ref: str, asset_type: str, asset_ref: str, process: str):
    return create_lineage_edge(
        session,
        get_or_create_node(session, "national_site", site_ref, site_ref),
        get_or_create_node(session, asset_type, asset_ref, asset_ref),
        "linked_to",
        process,
    )


def link_site_to_media(session, site_ref: str, media_ref: str):
    return _link_site_asset(session, site_ref, "media_asset", media_ref, "Media service")


def link_site_to_documents(session, site_ref: str, document_ref: str):
    return _link_site_asset(session, site_ref, "document", document_ref, "Document service")


def link_site_to_publication(session, site_ref: str, publication_ref: str):
    return create_lineage_edge(
        session,
        get_or_create_node(session, "national_site", site_ref, site_ref),
        get_or_create_node(session, "published_layer", publication_ref, publication_ref),
        "published_as",
        "Publication service",
    )
