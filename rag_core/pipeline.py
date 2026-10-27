"""Shared RAG entry points for the Django app and standalone examples."""

from dataclasses import replace

from . import providers
from .config import load_config, require_api_configuration, resolve_path
from .documents import chunk_documents, corpus_sha256, load_documents
from .errors import RAGError
from .lexical import LexicalIndex
from .vector import FaissIndex, read_bundle, write_bundle

DEMO_MODEL = "lexical-bm25-v1"


def _corpus(config):
    documents = load_documents(config.docs_dir)
    chunks = chunk_documents(documents, config.chunk_size, config.chunk_overlap)
    return documents, chunks, corpus_sha256(documents)


def build_index(folder=None, backend=None) -> dict:
    config = load_config()
    if folder is not None:
        config = replace(config, docs_dir=resolve_path(folder, config.root))
    if backend is not None:
        if backend not in {"demo", "openai"}:
            raise RAGError("configuration_error", "The requested backend must be demo or openai.")
        config = replace(config, backend=backend)
    if config.backend == "openai":
        require_api_configuration(config)
    documents, chunks, corpus_hash = _corpus(config)
    if not chunks:
        raise RAGError("empty_corpus", "The knowledge corpus contains no searchable text.")
    count = sum(bool(document.text.strip()) for document in documents)
    kwargs = {"corpus_sha256": corpus_hash, "document_count": count,
              "chunk_size": config.chunk_size, "chunk_overlap": config.chunk_overlap}
    if config.backend == "demo":
        write_bundle(config.index_dir, chunks, backend="demo", embedding_model=DEMO_MODEL, **kwargs)
    else:
        index = FaissIndex.build(chunks, providers.make_embeddings(config))
        index.save(config.index_dir, embedding_model=config.embedding_model, **kwargs)
    return {"backend": config.backend, "document_count": count, "chunk_count": len(chunks),
            "index_path": str(config.index_dir), "corpus_sha256": corpus_hash}


def _retrieval_query(question: str, history, maximum: int) -> str:
    # This is a transparent lexical follow-up heuristic, not semantic rewriting.
    markers = ("它", "那", "这", "多久", "多少", "呢", "吗", "it", "its", "that", "those", "they", "then", "what about", "how long")
    short = len(question) <= 40
    if short and any(marker in question.lower() for marker in markers):
        previous = next((item["content"] for item in reversed(providers.safe_history(history, maximum))
                         if item["role"] == "user" and item["content"].strip()), "")
        if previous:
            room = maximum - len(question) - 1
            if room > 0:
                return previous[:room] + " " + question
    return question


def _extractive_answer(sources: list[dict], lang: str, empty: bool = False) -> str:
    if not sources:
        if lang == "en":
            return ("The knowledge corpus is empty; add UTF-8 text documents." if empty
                    else "No matching evidence was found in the knowledge corpus.")
        return "知识库为空，请添加 UTF-8 文本文档。" if empty else "知识库中没有找到匹配证据，无法据此回答。"
    label = ("Local extractive demo (no language model generation):" if lang == "en"
             else "本地摘录演示（非大模型生成）：")
    return label + "\n\n" + "\n\n".join(f"[{item['source']} / {item['chunk_id']}]\n{item['text']}" for item in sources)


def answer(question, history=None, lang="zh") -> dict:
    config = load_config()
    if (not isinstance(question, str) or not question.strip() or len(question) > config.max_question_chars
            or not providers.is_valid_unicode(question)):
        raise RAGError("invalid_question", f"Question must be valid Unicode containing 1 to {config.max_question_chars} characters.")
    question = question.strip()
    lang = "en" if lang == "en" else "zh"
    if config.backend == "openai":
        require_api_configuration(config)
    _, chunks, corpus_hash = _corpus(config)
    query = _retrieval_query(question, history, config.max_question_chars)
    if config.backend == "demo":
        # Fresh installs run in memory. Existing saved bundles must pass validation.
        bundle_present = any((config.index_dir / name).exists() or (config.index_dir / name).is_symlink()
                             for name in ("manifest.json", "chunks.json", "index.faiss"))
        if bundle_present:
            saved_chunks, _, _ = read_bundle(config.index_dir, backend="demo", corpus_sha256=corpus_hash,
                                             embedding_model=DEMO_MODEL, chunk_size=config.chunk_size,
                                             chunk_overlap=config.chunk_overlap)
            if saved_chunks != chunks:
                raise RAGError("index_corrupt", "Saved citations do not match the current corpus. Rebuild the index.")
            chunks = saved_chunks
        sources = LexicalIndex(chunks).search(query, config.top_k)
        output = _extractive_answer(sources, lang, empty=not chunks)
        mode = "extractive_demo"
    else:
        index = FaissIndex.load(config.index_dir, providers.make_embeddings(config), corpus_sha256=corpus_hash,
                                embedding_model=config.embedding_model, chunk_size=config.chunk_size,
                                chunk_overlap=config.chunk_overlap)
        if index.chunks != chunks:
            raise RAGError("index_corrupt", "Saved citations do not match the current corpus. Rebuild the index.")
        sources = index.search(query, config.top_k, config.min_vector_score)
        output = (providers.generate_answer(config, question, sources, history, lang)
                  if sources else _extractive_answer([], lang, empty=not chunks))
        mode = "openai"
    return {"answer": output, "sources": sources, "mode": mode,
            "retrieval_query": query, "grounded": bool(sources)}
