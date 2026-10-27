"""Real FAISS persistence with deterministic local stub embeddings, never an API."""

import json

import pytest


class LocalEmbeddings:
    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0] if "returns" in text.lower() else [0.0, 1.0, 0.0]


def test_faiss_round_trip_preserves_sources_and_caps_k(tmp_path):
    pytest.importorskip("faiss")
    from rag_core.documents import Document, chunk_documents
    from rag_core.vector import FaissIndex

    chunks = chunk_documents([Document("returns.txt", "Returns within seven days"), Document("shipping.txt", "Shipping in two days")], 1000, 200)
    index = FaissIndex.build(chunks, LocalEmbeddings())
    index.save(tmp_path, corpus_sha256="a" * 64, embedding_model="local-stub", document_count=2, chunk_size=1000, chunk_overlap=200)
    assert (tmp_path / "index.faiss").is_file()
    assert (tmp_path / "chunks.json").is_file()
    assert not list(tmp_path.glob("*.pkl"))
    loaded = FaissIndex.load(tmp_path, LocalEmbeddings(), corpus_sha256="a" * 64, embedding_model="local-stub", chunk_size=1000, chunk_overlap=200)
    hits = loaded.search("returns", top_k=99, min_score=0.1)
    assert len(hits) == 1
    assert hits[0]["source"] == "returns.txt"
    assert hits[0]["text"] == "Returns within seven days"
    assert hits[0]["score"] == pytest.approx(1.0)


def test_faiss_rejects_binary_corruption_and_model_mismatch(tmp_path):
    pytest.importorskip("faiss")
    from rag_core.documents import Document, chunk_documents
    from rag_core.pipeline import RAGError
    from rag_core.vector import FaissIndex

    index = FaissIndex.build(chunk_documents([Document("a.txt", "returns")], 20, 2), LocalEmbeddings())
    kwargs = dict(corpus_sha256="b" * 64, embedding_model="local-stub", chunk_size=20, chunk_overlap=2)
    index.save(tmp_path, document_count=1, **kwargs)
    with pytest.raises(RAGError) as caught:
        FaissIndex.load(tmp_path, LocalEmbeddings(), **{**kwargs, "embedding_model": "other"})
    assert caught.value.code == "index_stale"
    (tmp_path / "index.faiss").write_bytes(b"broken binary")
    with pytest.raises(RAGError) as caught:
        FaissIndex.load(tmp_path, LocalEmbeddings(), **kwargs)
    assert caught.value.code == "index_corrupt"


def test_openai_pipeline_uses_one_chat_call_and_real_local_faiss(tmp_path, monkeypatch):
    pytest.importorskip("faiss")
    from rag_core import pipeline, providers

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "returns.txt").write_text("Returns within seven days", encoding="utf-8")
    monkeypatch.setenv("RAG_DOCS_DIR", str(docs))
    monkeypatch.setenv("RAG_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("RAG_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-offline-stub-value")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "offline-chat")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "local-stub")
    monkeypatch.setattr(providers, "make_embeddings", lambda config: LocalEmbeddings())
    calls = []
    def fake_generate(config, question, sources, history, lang="zh"):
        calls.append((question, sources, history))
        return "The policy says seven days."
    monkeypatch.setattr(providers, "generate_answer", fake_generate)
    built = pipeline.build_index()
    assert built["backend"] == "openai"
    result = pipeline.answer("returns", lang="en")
    assert len(calls) == 1
    assert result["mode"] == "openai"
    assert result["sources"][0]["source"] == "returns.txt"
    json.dumps(result)


def test_incompatible_optional_vector_installation_is_a_public_error(monkeypatch):
    import builtins
    from rag_core.documents import Document, chunk_documents
    from rag_core.pipeline import RAGError
    from rag_core.vector import FaissIndex

    original_import = builtins.__import__
    def incompatible(name, *args, **kwargs):
        if name == "faiss":
            raise ValueError("binary dependency traceback with private details")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", incompatible)
    with pytest.raises(RAGError) as caught:
        FaissIndex.build(chunk_documents([Document("a.txt", "returns")], 20, 2), LocalEmbeddings())
    assert caught.value.code == "missing_dependency"
    assert "private details" not in str(caught.value)


def test_provider_vectors_must_be_finite_and_nonzero():
    pytest.importorskip("faiss")
    from rag_core.documents import Document, chunk_documents
    from rag_core.pipeline import RAGError
    from rag_core.vector import FaissIndex

    class InvalidEmbeddings:
        def embed_documents(self, texts):
            return [[float("nan"), 0.0] for _ in texts]
    with pytest.raises(RAGError) as caught:
        FaissIndex.build(chunk_documents([Document("a.txt", "returns")], 20, 2), InvalidEmbeddings())
    assert caught.value.code == "provider_error"
