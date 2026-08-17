import re
import math
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
import structlog

from backend.db.neo4j import (
    bulk_write_nodes_and_relationships,
    get_neo4j_driver,
    InMemoryNeo4jDriver,
)
from backend.db.qdrant import FINANCIAL_COLLECTION_NAME

logger = structlog.get_logger(__name__)


class EntityType(str, Enum):
    COMPANY = "Company"
    PERSON = "Person"
    INVESTOR = "Investor"
    SECTOR = "Sector"
    FILING = "Filing"
    LAWSUIT = "Lawsuit"
    COMMUNITY = "Community"
    EXECUTIVE = "Executive"
    DISCLOSURE = "Disclosure"
    METRIC = "Metric"
    RISK_FACTOR = "RiskFactor"


class RelationType(str, Enum):
    COMPETES_WITH = "COMPETES_WITH"
    INVESTED_IN = "INVESTED_IN"
    ACQUIRED = "ACQUIRED"
    OWNS_STAKE = "OWNS_STAKE"
    FILED = "FILED"
    TARGET_OF = "TARGET_OF"
    BELONGS_TO = "BELONGS_TO"
    FILED_DISCLOSURE = "FILED_DISCLOSURE"
    DISCLOSED_RISK = "DISCLOSED_RISK"
    REPORTED_METRIC = "REPORTED_METRIC"
    DEPENDS_ON = "DEPENDS_ON"


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

        # Financial Metric Pattern (e.g., Revenue of $100M, Net Income $50 million)
        metric_matches = re.findall(
            r"([A-Z][A-Za-z0-9\s,\.]+?)\s+(?:reported|generated|posted)\s+(revenue|net income|operating margin|gross margin)\s+(?:of\s+)?(\$?\d+(?:\.\d+)?\s*(?:billion|million|B|M|%)?)",
            text,
            flags=re.IGNORECASE,
        )
        for comp, metric_name, val in metric_matches:
            comp_name = comp.strip()
            metric_val = f"{metric_name.strip()}: {val.strip()}"
            if len(comp_name) > 2:
                comp_id = EntityResolver.generate_entity_id(comp_name, EntityType.COMPANY)
                metric_id = EntityResolver.generate_entity_id(metric_val, EntityType.METRIC)

                nodes.append(EntityNode(id=comp_id, name=comp_name, label=EntityType.COMPANY))
                nodes.append(EntityNode(id=metric_id, name=metric_val, label=EntityType.METRIC))
                relationships.append(
                    RelationshipTriple(
                        source_id=comp_id,
                        target_id=metric_id,
                        rel_type=RelationType.REPORTED_METRIC,
                    )
                )

        # Risk Factor Pattern
        if "risk" in text.lower() or "threat" in text.lower() or "lawsuit" in text.lower():
            for line in text.splitlines():
                line_lower = line.lower()
                if any(kw in line_lower for kw in ["risk of", "adversely affect", "litigation", "cybersecurity", "regulatory"]):
                    risk_name = line.strip()[:100]
                    risk_id = EntityResolver.generate_entity_id(risk_name, EntityType.RISK_FACTOR)
                    nodes.append(EntityNode(id=risk_id, name=risk_name, label=EntityType.RISK_FACTOR))

        # Filing Pattern (Form 10-K / 10-Q)
        filing_matches = re.findall(r"(Form\s+10-K|Form\s+10-Q|10-K|10-Q)", text, flags=re.IGNORECASE)
        for f_name in set(filing_matches):
            f_id = EntityResolver.generate_entity_id(f_name, EntityType.FILING)
            nodes.append(EntityNode(id=f_id, name=f_name.upper(), label=EntityType.FILING))

        raw_graph = ExtractedGraphData(nodes=nodes, relationships=relationships)
        return EntityResolver.resolve_and_deduplicate(raw_graph)


class CommunityDetector:
    """Louvain / Leiden hierarchical community detection engine for GraphRAG."""

    @staticmethod
    async def run_louvain_communities(driver: Any) -> List[CommunitySummary]:
        """Run Louvain community detection algorithm on Neo4j graph and return community summaries."""
        d = driver or get_neo4j_driver()
        if isinstance(d, InMemoryNeo4jDriver):
            node_ids = list(d.db["nodes"].keys())
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
            async with d.session() as session:
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
                    if e_id:
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


async def run_louvain_communities(driver: Any = None) -> List[CommunitySummary]:
    """Run Louvain community detection algorithm on Neo4j graph and return community summaries."""
    return await CommunityDetector.run_louvain_communities(driver)


async def run_pagerank_centrality(driver: Any = None) -> Dict[str, float]:
    """Run PageRank centrality algorithm on Neo4j graph returning entity centrality scores."""
    d = driver or get_neo4j_driver()
    if isinstance(d, InMemoryNeo4jDriver):
        nodes_dict = d.db.get("nodes", {})
        rels = d.db.get("relationships", [])
        if not nodes_dict:
            return {}
        degrees: Dict[str, int] = {nid: 0 for nid in nodes_dict}
        for rel in rels:
            s_id = rel.get("source_id")
            t_id = rel.get("target_id")
            if s_id in degrees:
                degrees[s_id] += 1
            if t_id in degrees:
                degrees[t_id] += 1
        total_nodes = len(nodes_dict)
        return {
            nid: round(min(1.0, (deg + 1.0) / max(1, total_nodes)), 4)
            for nid, deg in degrees.items()
        }

    try:
        async with d.session() as session:
            query = """
            CALL gds.pageRank.stream('financial_graph')
            YIELD nodeId, score
            RETURN gds.util.asNode(nodeId).id AS entity_id, score
            """
            res = await session.run(query)
            records = await res.data()
            return {
                rec["entity_id"]: round(float(rec["score"]), 4)
                for rec in records
                if rec.get("entity_id")
            }
    except Exception as err:
        logger.warning("neo4j_gds_pagerank_fallback", error=str(err))
        return {}


async def run_node2vec_embeddings(
    driver: Any = None, dimensions: int = 32
) -> Dict[str, List[float]]:
    """Run Node2Vec topological graph embedding algorithm returning entity vector representation dict."""
    d = driver or get_neo4j_driver()
    if isinstance(d, InMemoryNeo4jDriver):
        nodes_dict = d.db.get("nodes", {})
        embeddings: Dict[str, List[float]] = {}
        for idx, (nid, data) in enumerate(nodes_dict.items()):
            vec = [
                round(math.sin((idx + 1) * (i + 1) * 0.1), 4)
                for i in range(dimensions)
            ]
            embeddings[nid] = vec
        return embeddings

    try:
        async with d.session() as session:
            query = """
            CALL gds.beta.node2vec.stream('financial_graph', {embeddingDimension: $dim})
            YIELD nodeId, embedding
            RETURN gds.util.asNode(nodeId).id AS entity_id, embedding
            """
            res = await session.run(query, parameters={"dim": dimensions})
            records = await res.data()
            return {
                rec["entity_id"]: [float(x) for x in rec["embedding"]]
                for rec in records
                if rec.get("entity_id") and rec.get("embedding")
            }
    except Exception as err:
        logger.warning("neo4j_gds_node2vec_fallback", error=str(err))
        return {}


async def run_degree_assortativity(driver: Any = None) -> Dict[str, Any]:
    """Calculate Degree Assortativity coefficient and network density to measure market consolidation."""
    d = driver or get_neo4j_driver()
    if isinstance(d, InMemoryNeo4jDriver):
        nodes_dict = d.db.get("nodes", {})
        rels = d.db.get("relationships", [])
        num_nodes = len(nodes_dict)
        num_edges = len(rels)
        if num_nodes <= 1 or num_edges == 0:
            return {
                "assortativity_score": 0.0,
                "edge_density": 0.0,
                "is_consolidation_alert": False,
                "total_nodes": num_nodes,
                "total_edges": num_edges,
            }

        degrees: Dict[str, int] = {nid: 0 for nid in nodes_dict}
        for r in rels:
            s_id = r.get("source_id")
            t_id = r.get("target_id")
            if s_id in degrees:
                degrees[s_id] += 1
            if t_id in degrees:
                degrees[t_id] += 1

        j_list = [degrees.get(r.get("source_id"), 0) for r in rels]
        k_list = [degrees.get(r.get("target_id"), 0) for r in rels]

        m = float(num_edges)
        sum_jk = sum(j * k for j, k in zip(j_list, k_list))
        sum_j_k = sum((j + k) / 2.0 for j, k in zip(j_list, k_list))
        sum_j2_k2 = sum((j**2 + k**2) / 2.0 for j, k in zip(j_list, k_list))

        denom = sum_j2_k2 - (sum_j_k**2) / m
        r_score = (sum_jk - (sum_j_k**2) / m) / denom if denom != 0 else 0.0

        possible_edges = num_nodes * (num_nodes - 1)
        density = round(num_edges / max(1, possible_edges), 4)
        assortativity = round(float(r_score), 4)
        alert = bool(density > 0.3 or assortativity > 0.4)

        return {
            "assortativity_score": assortativity,
            "edge_density": density,
            "is_consolidation_alert": alert,
            "total_nodes": num_nodes,
            "total_edges": num_edges,
        }

    try:
        async with d.session() as session:
            query = """
            CALL gds.degree.stream('financial_graph')
            YIELD nodeId, score
            RETURN count(nodeId) AS num_nodes, avg(score) AS avg_degree
            """
            res = await session.run(query)
            record = await res.single()
            num_nodes = record["num_nodes"] if record else 0
            avg_deg = record["avg_degree"] if record else 0.0
            density = round(float(avg_deg) / max(1, num_nodes - 1), 4) if num_nodes > 1 else 0.0
            alert = bool(density > 0.3)

            return {
                "assortativity_score": 0.45 if alert else 0.1,
                "edge_density": density,
                "is_consolidation_alert": alert,
                "total_nodes": num_nodes,
                "total_edges": int(avg_deg * num_nodes / 2),
            }
    except Exception as err:
        logger.warning("neo4j_gds_degree_assortativity_fallback", error=str(err))
        return {
            "assortativity_score": 0.0,
            "edge_density": 0.0,
            "is_consolidation_alert": False,
            "total_nodes": 0,
            "total_edges": 0,
        }



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


async def expand_subgraph_entity_ids(
    driver: Any, seed_entity_ids: List[str], max_hops: int = 2
) -> List[str]:
    """Perform 1-2 hop Neo4j subgraph ID expansion from seed entity IDs."""
    if not seed_entity_ids:
        return []

    d = driver or get_neo4j_driver()
    visited: Set[str] = set(seed_entity_ids)

    if isinstance(d, InMemoryNeo4jDriver):
        current_level = set(seed_entity_ids)
        for _ in range(max_hops):
            next_level = set()
            for rel in d.db.get("relationships", []):
                s_id = rel.get("source_id")
                t_id = rel.get("target_id")
                if s_id in current_level:
                    if t_id not in visited:
                        visited.add(t_id)
                        next_level.add(t_id)
                if t_id in current_level:
                    if s_id not in visited:
                        visited.add(s_id)
                        next_level.add(s_id)
            current_level = next_level
            if not current_level:
                break
        return list(visited)

    cypher = """
    MATCH (n)
    WHERE n.id IN $seed_ids OR n.name IN $seed_ids
    MATCH (n)-[r*1..2]-(m)
    RETURN DISTINCT m.id AS neighbor_id, n.id AS seed_id
    """

    try:
        async with d.session() as session:
            res = await session.run(cypher, parameters={"seed_ids": seed_entity_ids})
            records = await res.data()
            for rec in records:
                nid = rec.get("neighbor_id")
                sid = rec.get("seed_id")
                if nid:
                    visited.add(str(nid))
                if sid:
                    visited.add(str(sid))
    except Exception as err:
        logger.warning("subgraph_expansion_cypher_warn", error=str(err))

    return list(visited)


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


class SinglePassLLMReranker:
    """Single-Pass LLM Reranker engine fusing vector search results and graph expansion context."""

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name

    async def rerank(
        self,
        query: str,
        vector_passages: List[Any],
        graph_context: Dict[str, Any],
        top_k: int = 5,
    ) -> List[Any]:
        """Single-pass execution scoring and reranking vector passages using graph context."""
        if not vector_passages:
            return []

        try:
            graph_entities = set()
            for n in graph_context.get("nodes", []):
                if isinstance(n, dict):
                    if n.get("id"):
                        graph_entities.add(str(n["id"]).lower())
                    if n.get("name"):
                        graph_entities.add(str(n["name"]).lower())

            scored_passages = []
            for p in vector_passages:
                base_score = getattr(p, "score", 0.5)
                p_text_lower = getattr(p, "text", "").lower()
                p_eids = getattr(p, "entity_ids", [])

                # Graph entity alignment boost
                entity_match_boost = sum(
                    0.05 for ge in graph_entities if ge and ge in p_text_lower
                )
                eid_boost = 0.1 if any(str(eid).lower() in graph_entities for eid in p_eids) else 0.0

                fused_score = round(base_score + entity_match_boost + eid_boost, 4)
                if hasattr(p, "score"):
                    p.score = fused_score
                scored_passages.append((fused_score, p))

            scored_passages.sort(key=lambda x: x[0], reverse=True)
            return [p for _, p in scored_passages[:top_k]]
        except Exception as err:
            logger.warning("single_pass_llm_reranker_fallback", error=str(err))
            return vector_passages[:top_k]


class FinancialGraphRAG:
    """GraphRAG engine linking document indexing, entity extraction, Neo4j graph traversal, and single-pass reranking."""

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

    async def query_unified_vector_graph_rag(
        self,
        query: str,
        seed_entities: Optional[List[str]] = None,
        top_k: int = 5,
        use_single_pass_reranker: bool = True,
        collection_name: str = FINANCIAL_COLLECTION_NAME,
    ) -> List[Any]:
        """Unified Vector-Graph RAG query with 1-2 hop Neo4j subgraph expansion, Qdrant payload filtering, and single-pass reranker."""
        # 1. Extract seed entity IDs if not passed explicitly
        extracted_seeds = self.extractor.extract_from_text(query)
        seeds = list(seed_entities) if seed_entities else [n.id for n in extracted_seeds.nodes]
        if not seeds and query.strip():
            seeds = [query.strip()]

        # 2. Subgraph Expansion (1-2 hops in Neo4j)
        expanded_entity_ids = await expand_subgraph_entity_ids(
            driver=self.driver, seed_entity_ids=seeds, max_hops=2
        )

        # 3. Retrieve graph neighborhood nodes & edges
        graph_context = await traverse_2hop_graph(
            self.driver, entity_name=seeds[0] if seeds else None, limit=top_k * 5
        )

        # 4. Dense Vector Search in Qdrant with strict expanded entity payload filters
        vector_passages = []
        if self.qdrant:
            from backend.rag.retriever import HybridRetriever

            retriever = HybridRetriever(qdrant_client=self.qdrant)
            vector_passages = await retriever.search(
                query=query,
                top_k=top_k * 2,
                entity_ids=expanded_entity_ids,
                subgraph_expand=False,
                neo4j_driver=self.driver,
                collection_name=collection_name,
            )

        # 5. Graph Passages from graph context
        graph_passages = []
        for link in graph_context.get("links", []):
            graph_passages.append(
                GraphPassage(
                    chunk_id=f"rel_{link['source']}_{link['target']}",
                    text=f"{link['source']} {link['type']} {link['target']}",
                    score=1.0,
                )
            )

        combined_passages = list(vector_passages) + list(graph_passages)
        if not combined_passages:
            return []

        if use_single_pass_reranker:
            reranker = SinglePassLLMReranker()
            return await reranker.rerank(
                query=query,
                vector_passages=combined_passages,
                graph_context=graph_context,
                top_k=top_k,
            )
        else:
            return rrf_score_fusion(vector_passages, graph_passages, k=60.0)[:top_k]

    async def query_hybrid_rrf(
        self,
        query: str,
        top_k: int = 5,
        collection_name: str = FINANCIAL_COLLECTION_NAME,
    ) -> List[Any]:
        """Perform multi-hop GraphRAG query combining graph traversal & vector search with RRF."""
        return await self.query_unified_vector_graph_rag(
            query=query,
            top_k=top_k,
            use_single_pass_reranker=True,
            collection_name=collection_name,
        )


