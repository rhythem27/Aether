#!/usr/bin/env python3
"""
Batch Folder Ingestion CLI for Required Documents.
Traverses required_docs/ subdirectories, parses documents using AnyDocParser,
chunks content via TokenAwareChunker, and indexes vectors into Qdrant.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import structlog

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.rag.anydoc_parser import AnyDocParser
from backend.rag.chunking import TokenAwareChunker
from backend.rag.retriever import HybridRetriever
from backend.db.qdrant import get_qdrant_client, init_qdrant_collection

logger = structlog.get_logger(__name__)

DOC_CATEGORY_MAPPING = {
    "sec_filings": "sec_filing",
    "pitch_decks": "pitch_deck",
    "news_and_press": "press_release",
    "legal_and_court": "legal_filing",
    "financial_statements": "financial_statement",
}


def find_required_docs_dir(given_path: Optional[str] = None) -> Path:
    """Resolve required_docs directory location."""
    if given_path:
        p = Path(given_path).resolve()
        if p.exists():
            return p

    candidates = [
        Path("building-base/aether/required_docs"),
        Path("required_docs"),
        Path("../building-base/aether/required_docs"),
    ]
    for cand in candidates:
        abs_cand = cand.resolve()
        if abs_cand.exists():
            return abs_cand

    raise FileNotFoundError(
        "Could not locate required_docs directory. Please pass --docs-dir explicitly."
    )


async def process_and_ingest(
    docs_dir: Path,
    company_ticker: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    dry_run: bool = False,
    output_dir: Optional[str] = None,
    qdrant_url: Optional[str] = None,
) -> Dict[str, int]:
    """Traverse directories, parse docs, chunk, and index."""
    parser = AnyDocParser()
    chunker = TokenAwareChunker(max_tokens=512, overlap=50)

    stats = {
        "files_processed": 0,
        "files_failed": 0,
        "total_chunks": 0,
        "total_upserted": 0,
    }

    retriever = None
    q_client = None

    if not dry_run:
        try:
            q_client = get_qdrant_client(url=qdrant_url)
            await init_qdrant_collection(client=q_client)
            retriever = HybridRetriever(qdrant_client=q_client)
        except Exception as err:
            logger.warning(
                "qdrant_connection_unavailable_switching_to_dry_run", error=str(err)
            )
            dry_run = True

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

    for category_dir, doc_type in DOC_CATEGORY_MAPPING.items():
        sub_path = docs_dir / category_dir
        if not sub_path.exists():
            logger.info("subfolder_not_found_skipping", path=str(sub_path))
            continue

        for file_path in sub_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                logger.info(
                    "ingesting_file",
                    file_path=str(file_path),
                    category=category_dir,
                    doc_type=doc_type,
                )
                try:
                    parsed_doc = parser.parse(
                        file_path=str(file_path),
                        company_ticker=company_ticker,
                        fiscal_year=fiscal_year,
                        doc_category=doc_type,
                    )

                    chunks = chunker.chunk_document(
                        document=parsed_doc,
                        company_ticker=company_ticker,
                        fiscal_year=fiscal_year,
                        document_type=doc_type,
                    )

                    stats["files_processed"] += 1
                    stats["total_chunks"] += len(chunks)

                    # Save markdown output if output_dir provided
                    if output_dir:
                        out_file = Path(output_dir) / f"{file_path.stem}.md"
                        out_file.write_text(parsed_doc.raw_text, encoding="utf-8")
                        logger.info("saved_markdown_output", path=str(out_file))

                    # Extract and index Neo4j GraphRAG entity triples
                    try:
                        from backend.rag.graphrag import FinancialGraphRAG
                        graph_rag = FinancialGraphRAG(qdrant_client=q_client)
                        graph_data = await graph_rag.index_document_graph(
                            text=parsed_doc.raw_text, source_id=file_path.name
                        )
                        stats["graph_nodes"] = stats.get("graph_nodes", 0) + len(graph_data.nodes)
                        stats["graph_relationships"] = stats.get("graph_relationships", 0) + len(graph_data.relationships)
                    except Exception as graph_err:
                        logger.warning("graphrag_indexing_warning", filename=file_path.name, error=str(graph_err))

                    # Upsert into Qdrant if live
                    if retriever and not dry_run:
                        upserted_count = await retriever.upsert_chunks(chunks)
                        stats["total_upserted"] += upserted_count
                        logger.info(
                            "upserted_chunks_to_qdrant",
                            filename=file_path.name,
                            count=upserted_count,
                        )

                except Exception as exc:
                    stats["files_failed"] += 1
                    logger.error(
                        "failed_to_process_file", file_path=str(file_path), error=str(exc)
                    )

    if q_client:
        await q_client.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Phase 10A Required Docs Ingestion Engine"
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        help="Path to required_docs directory (default: auto-detect)",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default="AETHER",
        help="Default company ticker metadata",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Default fiscal year metadata",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and chunk documents without indexing into Qdrant",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Optional output directory to dump clean Markdown parsed files",
    )
    parser.add_argument(
        "--qdrant-url",
        type=str,
        help="Override Qdrant server URL",
    )

    args = parser.parse_args()

    docs_path = find_required_docs_dir(args.docs_dir)
    print(f"Target Document Directory: {docs_path}")
    print(f"Execution Mode: {'DRY RUN (No Qdrant Upsert)' if args.dry_run else 'LIVE INGESTION'}")

    stats = asyncio.run(
        process_and_ingest(
            docs_dir=docs_path,
            company_ticker=args.ticker,
            fiscal_year=args.year,
            dry_run=args.dry_run,
            output_dir=args.output_dir,
            qdrant_url=args.qdrant_url,
        )
    )

    print("\nIngestion Results Summary:")
    print(f"  * Files Processed:     {stats['files_processed']}")
    print(f"  * Files Failed:        {stats['files_failed']}")
    print(f"  * Total Chunks:        {stats['total_chunks']}")
    print(f"  * Total Upserted:      {stats['total_upserted']}")
    print(f"  * Graph Nodes:         {stats.get('graph_nodes', 0)}")
    print(f"  * Graph Relationships: {stats.get('graph_relationships', 0)}")


if __name__ == "__main__":
    main()
