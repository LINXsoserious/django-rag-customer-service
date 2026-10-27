"""A small deterministic retrieval example using the shared implementation.

This default example performs real retrieval and prints source excerpts. It does
not call an LLM or pretend that deterministic excerpts are generated answers.
"""
from __future__ import annotations

import argparse
import json
import sys

from rag_core.documents import Document, chunk_documents
from rag_core.lexical import LexicalIndex


def run(question: str, top_k: int = 2) -> dict:
    documents = [
        Document(source="demo/returns.txt", text="Fictional NovaShop accepts returns within 14 days. 虚构NovaShop支持签收后14天内退货。"),
        Document(source="demo/shipping.txt", text="Fictional delivery takes 3 to 5 business days. 虚构配送需要3至5个工作日。"),
        Document(source="demo/support.txt", text="Fictional support is open Monday to Friday. 虚构客服在周一至周五开放。"),
    ]
    chunks = chunk_documents(documents, chunk_size=1000, chunk_overlap=200)
    sources = LexicalIndex(chunks).search(question, top_k=top_k)
    return {"mode": "retrieval_only_demo", "question": question, "chunk_count": len(chunks),
            "sources": sources, "generation_calls": 0,
            "note": "Inspect the exact source spans; use the main pipeline for extractive demo or explicitly configured API generation."}


def main(argv=None):
    # JSON is a UTF-8 interface even when the host terminal defaults to cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Trace a small handwritten RAG retrieval loop without an API")
    parser.add_argument("--question", default="退货期限是多少？ returns")
    parser.add_argument("--top-k", type=int, default=2)
    args = parser.parse_args(argv)
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20")
    print(json.dumps(run(args.question, args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
