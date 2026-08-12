import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
import structlog

from backend.db.neo4j import (
    bulk_write_nodes_and_relationships,
    get_neo4j_driver,
    InMemoryNeo4jDriver,
)

logger = structlog.get_logger(__name__)


class EntityType(str, Enum):
    COMPANY = "Company"
    PERSON = "Person"
    INVESTOR = "Investor"
    SECTOR = "Sector"
    FILING = "Filing"
    LAWSUIT = "Lawsuit"
    COMMUNITY = "Community"


class RelationType(str, Enum):
    COMPETES_WITH = "COMPETES_WITH"
    INVESTED_IN = "INVESTED_IN"
    ACQUIRED = "ACQUIRED"
    OWNS_STAKE = "OWNS_STAKE"
    FILED = "FILED"
    TARGET_OF = "TARGET_OF"
    BELONGS_TO = "BELONGS_TO"


class EntityNode(BaseModel):
    id: str
    name: str
    label: EntityType
    properties: Dict[str, Any] = Field(default_factory=dict)


class RelationshipTriple(BaseModel):
    source_id: str
    target_id: str
    rel_type: RelationType
    properties: Dict[str, Any] = Field(default_factory=dict)


class ExtractedGraphData(BaseModel):
    nodes: List[EntityNode] = Field(default_factory=list)
    relationships: List[RelationshipTriple] = Field(default_factory=list)


class CommunitySummary(BaseModel):
    community_id: str
    level: int = 1
    summary_text: str
    entity_ids: List[str] = Field(default_factory=list)


class GraphPassage(BaseModel):
    chunk_id: str
    text: str
    score: float = 1.0


class EntityResolver:
    """Entity resolution & deduplication engine for canonicalizing financial entity names."""

    TICKER_MAP = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "NVDA": "NVIDIA Corporation",
        "TSLA": "Tesla Inc.",
        "AMZN": "Amazon.com Inc.",
        "GOOGL": "Alphabet Inc.",
        "META": "Meta Platforms Inc.",
    }

    @classmethod
    def canonicalize_name(cls, raw_name: str) -> str:
        clean = raw_name.strip()
        upper = clean.upper()
        if upper in cls.TICKER_MAP:
            return cls.TICKER_MAP[upper]
        return clean

    @classmethod
    def generate_entity_id(cls, name: str, entity_type: EntityType) -> str:
        canonical = cls.canonicalize_name(name).lower()
        clean_slug = re.sub(r"[^\w]+", "_", canonical).strip("_")
        return f"{entity_type.value.lower()}_{clean_slug}"

    @classmethod
    def resolve_and_deduplicate(
        cls, extracted: ExtractedGraphData
    ) -> ExtractedGraphData:
        """Deduplicate nodes and merge relationship triples."""
        node_map: Dict[str, EntityNode] = {}
        for node in extracted.nodes:
            canonical_name = cls.canonicalize_name(node.name)
            entity_id = cls.generate_entity_id(canonical_name, node.label)

            if entity_id in node_map:
                node_map[entity_id].properties.update(node.properties)
            else:
                node_map[entity_id] = EntityNode(
                    id=entity_id,
                    name=canonical_name,
                    label=node.label,
                    properties=node.properties,
                )

        rel_set: Set[Tuple[str, str, str]] = set()
        resolved_rels: List[RelationshipTriple] = []

        for rel in extracted.relationships:
            triple_key = (rel.source_id, rel.target_id, rel.rel_type.value)
            if triple_key not in rel_set:
                rel_set.add(triple_key)
                resolved_rels.append(rel)

        return ExtractedGraphData(
            nodes=list(node_map.values()), relationships=resolved_rels
        )


class EntityExtractor:
    """Structured entity and relationship extractor for financial documents."""

    def extract_from_text(self, text: str) -> ExtractedGraphData:
        nodes: List[EntityNode] = []
        relationships: List[RelationshipTriple] = []

        # Acquisition Pattern
        acquisition_matches = re.findall(
            r"([A-Z][A-Za-z0-9\s,\.]+?)\s+(?:acquired|purchased|bought)\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s+for|\.|$)",
            text,
        )
        for buyer, target in acquisition_matches:
            b_name = buyer.strip()
            t_name = target.strip()
            if len(b_name) > 2 and len(t_name) > 2:
                b_id = EntityResolver.generate_entity_id(b_name, EntityType.COMPANY)
                t_id = EntityResolver.generate_entity_id(t_name, EntityType.COMPANY)

                nodes.append(EntityNode(id=b_id, name=b_name, label=EntityType.COMPANY))
                nodes.append(EntityNode(id=t_id, name=t_name, label=EntityType.COMPANY))
                relationships.append(
                    RelationshipTriple(
                        source_id=b_id, target_id=t_id, rel_type=RelationType.ACQUIRED
                    )
                )

        # Investment Pattern
        investment_matches = re.findall(
            r"([A-Z][A-Za-z0-9\s,\.]+?)\s+(?:invested in|led funding for|participated in)\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s+|\.|$)",
            text,
        )
        for inv, comp in investment_matches:
            inv_name = inv.strip()
            comp_name = comp.strip()
            if len(inv_name) > 2 and len(comp_name) > 2:
                inv_id = EntityResolver.generate_entity_id(
                    inv_name, EntityType.INVESTOR
                )
                comp_id = EntityResolver.generate_entity_id(
                    comp_name, EntityType.COMPANY
                )

                nodes.append(
                    EntityNode(id=inv_id, name=inv_name, label=EntityType.INVESTOR)
                )
                nodes.append(
                    EntityNode(id=comp_id, name=comp_name, label=EntityType.COMPANY)
                )
                relationships.append(
                    RelationshipTriple(
                        source_id=inv_id,
                        target_id=comp_id,
                        rel_type=RelationType.INVESTED_IN,
                    )
                )

        # Competition Pattern
        compete_matches = re.findall(
            r"([A-Z][A-Za-z0-9\s,\.]+?)\s+(?:competes with|is a competitor of)\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s+|\.|$)",
            text,
        )
        for c1, c2 in compete_matches:
            c1_name = c1.strip()
            c2_name = c2.strip()
            if len(c1_name) > 2 and len(c2_name) > 2:
                c1_id = EntityResolver.generate_entity_id(c1_name, EntityType.COMPANY)
                c2_id = EntityResolver.generate_entity_id(c2_name, EntityType.COMPANY)

                nodes.append(
                    EntityNode(id=c1_id, name=c1_name, label=EntityType.COMPANY)
                )
                nodes.append(
                    EntityNode(id=c2_id, name=c2_name, label=EntityType.COMPANY)
                )
                relationships.append(
                    RelationshipTriple(
                        source_id=c1_id,
                        target_id=c2_id,
                        rel_type=RelationType.COMPETES_WITH,
                    )
                )

        raw_graph = ExtractedGraphData(nodes=nodes, relationships=relationships)
        return EntityResolver.resolve_and_deduplicate(raw_graph)


class CommunityDetector:
    """Louvain / Leiden hierarchical community detection engine for GraphRAG."""

    @staticmethod
    async def run_louvain_communities(driver: Any) -> List[CommunitySummary]:
        """Run Louvain community detection algorithm on Neo4j graph and return community summaries."""
        if isinstance(driver, InMemoryNeo4jDriver):
            # Fallback clustering for in-memory graph driver
            node_ids = list(driver.db["nodes"].keys())
            if not node_ids:
                return []
            comm_id = "community_lvl1_0"
            summary_text = (
                f"Financial cluster containing entities: {', '.join(node_ids[:5])}"
            )
            return [
                CommunitySummary(
                    community_id=comm_id,
                    level=1,
                    summary_text=summary_text,
                    entity_ids=node_ids,
                )
            ]

        try:
            async with driver.session() as session:
                query = """
                CALL gds.louvain.stream('financial_graph')
                YIELD nodeId, communityId
                RETURN gds.util.asNode(nodeId).id AS entity_id, communityId
                """
                res = await session.run(query)
                records = await res.data()

                community_groups: Dict[int, List[str]] = {}
                for rec in records:
                    comm_id = rec["communityId"]
                    e_id = rec["entity_id"]
                    community_groups.setdefault(comm_id, []).append(e_id)

                summaries = []
                for cid, e_list in community_groups.items():
                    summaries.append(
                        CommunitySummary(
                            community_id=f"community_lvl1_{cid}",
                            level=1,
                            summary_text=f"Louvain Community {cid} comprising: {', '.join(e_list[:5])}",
                            entity_ids=e_list,
                        )
                    )
                return summaries
        except Exception as err:
            logger.warning("neo4j_gds_louvain_fallback", error=str(err))
            return []


def rrf_score_fusion(
    vector_passages: List[Any], graph_passages: List[Any], k: float = 60.0
) -> List[Any]:
    """Reciprocal Rank Fusion (RRF) algorithm merging vector scores and graph traversal scores."""
    rrf_map: Dict[str, float] = {}
    passage_map: Dict[str, Any] = {}

    # Rank vector passages
    for rank, p in enumerate(vector_passages):
        p_id = getattr(p, "chunk_id", str(id(p)))
        passage_map[p_id] = p
        rrf_map[p_id] = rrf_map.get(p_id, 0.0) + (1.0 / (k + rank + 1))

    # Rank graph passages
    for rank, p in enumerate(graph_passages):
        p_id = getattr(p, "chunk_id", str(id(p)))
        passage_map[p_id] = p
        rrf_map[p_id] = rrf_map.get(p_id, 0.0) + (1.0 / (k + rank + 1))

    # Sort items by combined RRF score descending
    sorted_p_ids = sorted(rrf_map.keys(), key=lambda pid: rrf_map[pid], reverse=True)

    result = []
    for pid in sorted_p_ids:
        passage = passage_map[pid]
        # Attach updated RRF score
        if hasattr(passage, "score"):
            passage.score = round(rrf_map[pid], 6)
        result.append(passage)

    return result


async def traverse_2hop_graph(
    driver: Any, entity_name: Optional[str] = None, limit: int = 50
) -> Dict[str, Any]:
    """Retrieve 2-hop neighborhood nodes and relationship edges from Neo4j."""
    nodes_dict: Dict[str, Dict[str, Any]] = {}
    links_list: List[Dict[str, Any]] = []

    if isinstance(driver, InMemoryNeo4jDriver):
        nodes_list = [
            {"id": nid, "label": data["label"], "properties": data["properties"]}
            for nid, data in driver.db["nodes"].items()
        ][:limit]
        links_list = [
            {
                "source": r["source_id"],
                "target": r["target_id"],
                "type": r["rel_type"],
                "properties": r.get("properties", {}),
            }
            for r in driver.db["relationships"]
        ][:limit]
        return {"nodes": nodes_list, "links": links_list}

    cypher = """
    MATCH (n)-[r1]-(m)-[r2]-(p)
    WHERE $entity_name IS NULL OR n.name = $entity_name OR n.id = $entity_name
    RETURN n, r1, m, r2, p
    LIMIT $limit
    """

    try:
        async with driver.session() as session:
            res = await session.run(
                cypher, parameters={"entity_name": entity_name, "limit": limit}
            )
            records = await res.data()

            for rec in records:
                for node_key in ["n", "m", "p"]:
                    node = rec.get(node_key)
                    if node:
                        node_id = node.get("id", str(node.id))
                        labels = (
                            list(node.labels) if hasattr(node, "labels") else ["Entity"]
                        )
                        nodes_dict[node_id] = {
                            "id": node_id,
                            "label": labels[0] if labels else "Entity",
                            "name": node.get("name", node_id),
                            "properties": dict(node),
                        }
                for rel_key in ["r1", "r2"]:
                    rel = rec.get(rel_key)
                    if rel:
                        links_list.append(
                            {
                                "source": rel.start_node.get(
                                    "id", str(rel.start_node.id)
                                ),
                                "target": rel.end_node.get("id", str(rel.end_node.id)),
                                "type": rel.type,
                                "properties": dict(rel),
                            }
                        )
    except Exception as err:
        logger.warning("neo4j_graph_traverse_fallback", error=str(err))

    return {"nodes": list(nodes_dict.values()), "links": links_list}


class FinancialGraphRAG:
    """GraphRAG engine linking document indexing, entity extraction, and Neo4j graph traversal."""

    def __init__(self, neo4j_driver=None, qdrant_client=None):
        self.driver = neo4j_driver or get_neo4j_driver()
        self.qdrant = qdrant_client
        self.extractor = EntityExtractor()

    async def index_document_graph(
        self, text: str, source_id: Optional[str] = None
    ) -> ExtractedGraphData:
        """Extract entities & relationships from text and commit to Neo4j graph store."""
        extracted = self.extractor.extract_from_text(text)

        if extracted.nodes or extracted.relationships:
            nodes_dicts = [
                {
                    "id": n.id,
                    "name": n.name,
                    "label": n.label.value,
                    "properties": n.properties,
                }
                for n in extracted.nodes
            ]
            rels_dicts = [
                {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "rel_type": r.rel_type.value,
                    "properties": r.properties,
                }
                for r in extracted.relationships
            ]

            await bulk_write_nodes_and_relationships(
                nodes=nodes_dicts, relationships=rels_dicts, driver=self.driver
            )

        logger.info(
            "document_graph_indexed",
            num_nodes=len(extracted.nodes),
            num_rels=len(extracted.relationships),
        )
        return extracted

    async def query_hybrid_rrf(self, query: str, top_k: int = 5) -> List[Any]:
        """Perform multi-hop GraphRAG query combining graph traversal & vector search with RRF."""
        # 1. Traversal in Neo4j graph
        graph_data = await traverse_2hop_graph(
            self.driver, entity_name=query, limit=top_k
        )

        graph_passages = []
        for link in graph_data.get("links", []):
            graph_passages.append(
                GraphPassage(
                    chunk_id=f"rel_{link['source']}_{link['target']}",
                    text=f"{link['source']} {link['type']} {link['target']}",
                    score=1.0,
                )
            )

        # 2. Vector search if Qdrant is available
        vector_passages = []
        if self.qdrant:
            from backend.rag.retriever import HybridRetriever

            retriever = HybridRetriever(qdrant_client=self.qdrant)
            vector_passages = await retriever.search(query, top_k=top_k)

        # 3. Fuse via Reciprocal Rank Fusion
        return rrf_score_fusion(vector_passages, graph_passages, k=60.0)[:top_k]
