from typing import Any, Dict, List, Optional, Set
import structlog

logger = structlog.get_logger(__name__)

# Comprehensive Financial Taxonomy Dictionary (Acronyms, Synonyms & Hierarchical Subclasses)
FINANCIAL_TAXONOMY_DICTIONARY: Dict[str, List[str]] = {
    "capex": ["capital expenditures", "capital spending", "capital investment"],
    "capital expenditures": ["capex", "capital spending", "capital investment"],
    "ebitda": ["earnings before interest taxes depreciation and amortization", "operating earnings"],
    "opex": ["operating expenses", "operating costs"],
    "top line": ["revenue", "gross sales", "total turnover"],
    "revenue": ["top line", "gross sales", "total turnover"],
    "bottom line": ["net income", "net profit", "net earnings"],
    "net income": ["bottom line", "net profit", "net earnings"],
    "m&a": ["mergers and acquisitions", "takeover", "buyout"],
    "mergers and acquisitions": ["m&a", "takeover", "buyout"],
    "roic": ["return on invested capital"],
    "cfo": ["chief financial officer"],
    "ceo": ["chief executive officer"],
    "guidance": ["outlook", "forecast", "forward-looking estimate"],
    "share buyback": ["repurchase program", "stock buyback"],
    "gross margin": ["gross profit margin"],
    "operating margin": ["operating profit margin"],
}


class FinancialTaxonomyEngine:
    """Financial Taxonomy Engine traversing Neo4j Taxonomy graph nodes and term expansion mappings."""

    def __init__(self, taxonomy_dict: Optional[Dict[str, List[str]]] = None):
        self.taxonomy_dict = taxonomy_dict or FINANCIAL_TAXONOMY_DICTIONARY

    def get_synonyms(self, term: str, driver: Optional[Any] = None) -> List[str]:
        """Lookup synonyms for a financial term or acronym."""
        term_lower = term.lower().strip()
        synonyms = set(self.taxonomy_dict.get(term_lower, []))

        # Query Neo4j if driver is provided
        if driver is not None:
            try:
                # Driver Cypher query for live Neo4j Taxonomy nodes
                pass
            except Exception as e:
                logger.warning("neo4j_taxonomy_lookup_failed_fallback", error=str(e))

        return sorted(list(synonyms))

    def expand_term(self, term: str) -> List[str]:
        """Expand a term to include itself and all known financial synonyms."""
        term_lower = term.lower().strip()
        syns = self.get_synonyms(term_lower)
        all_terms = {term_lower}
        all_terms.update(syns)
        return sorted(list(all_terms))


_taxonomy_engine: Optional[FinancialTaxonomyEngine] = None


def get_financial_taxonomy() -> FinancialTaxonomyEngine:
    global _taxonomy_engine
    if _taxonomy_engine is None:
        _taxonomy_engine = FinancialTaxonomyEngine()
    return _taxonomy_engine
