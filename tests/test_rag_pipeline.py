"""The default path must remain keyless, local, and honest about extraction."""

import json

import pytest


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "returns.txt").write_text("Returns are accepted within seven days. 退货政策：收货后七天内申请。", encoding="utf-8")
    (docs / "shipping.txt").write_text("Shipping takes two business days. 物流发货需要两个工作日。", encoding="utf-8")
    monkeypatch.setenv("RAG_DOCS_DIR", str(docs))
    monkeypatch.setenv("RAG_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("RAG_BACKEND", "demo")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return docs, tmp_path / "index"


def test_default_answer_is_real_local_extraction_without_provider_calls(corpus, monkeypatch):
    from rag_core import pipeline, providers

    def forbidden(*args, **kwargs):
        raise AssertionError("Demo must not construct an API provider")

    monkeypatch.setattr(providers, "make_embeddings", forbidden)
    monkeypatch.setattr(providers, "generate_answer", forbidden)
    result = pipeline.answer("退货政策", lang="zh")
    assert result["mode"] == "extractive_demo"
    assert result["grounded"] is True
    assert "摘录" in result["answer"]
    assert result["sources"][0]["source"] == "returns.txt"
    assert "七天" in result["sources"][0]["text"]
    assert str(corpus[0]) not in json.dumps(result, ensure_ascii=False)


def test_no_hits_and_empty_corpus_do_not_invent_answers(corpus):
    from rag_core.pipeline import answer

    result = answer("quantumbanana", lang="en")
    assert result["sources"] == []
    assert result["grounded"] is False
    assert "no matching" in result["answer"].lower()
    for p in corpus[0].glob("*.txt"):
        p.unlink()
    result = answer("returns", lang="en")
    assert result["sources"] == []
    assert "empty" in result["answer"].lower()


def test_built_demo_index_rejects_changed_corpus_and_corrupt_metadata(corpus):
    from rag_core.pipeline import RAGError, answer, build_index

    built = build_index()
    assert built["backend"] == "demo"
    assert built["document_count"] == 2
    assert built["chunk_count"] == 2
    assert len(built["corpus_sha256"]) == 64
    assert (corpus[1] / "manifest.json").is_file()
    assert answer("returns")["grounded"]
    (corpus[0] / "new.txt").write_text("New knowledge", encoding="utf-8")
    with pytest.raises(RAGError) as caught:
        answer("returns")
    assert caught.value.code == "index_stale"
    build_index()
    (corpus[1] / "chunks.json").write_text("[]", encoding="utf-8")
    with pytest.raises(RAGError) as caught:
        answer("returns")
    assert caught.value.code == "index_corrupt"


def test_partial_demo_bundle_is_not_silently_rebuilt(corpus):
    from rag_core.pipeline import RAGError, answer, build_index

    build_index()
    (corpus[1] / "manifest.json").unlink()
    with pytest.raises(RAGError) as caught:
        answer("returns")
    assert caught.value.code in {"index_missing", "index_corrupt"}


def test_saved_citation_text_must_still_match_the_current_corpus(corpus):
    import hashlib
    from rag_core.pipeline import RAGError, answer, build_index

    build_index()
    chunks_path = corpus[1] / "chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks[0]["text"] = "X" * len(chunks[0]["text"])
    chunks_path.write_text(json.dumps(chunks), encoding="utf-8")
    manifest_path = corpus[1] / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["chunks.json"] = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RAGError) as caught:
        answer("returns")
    assert caught.value.code == "index_corrupt"


@pytest.mark.parametrize("question", ["", "  ", "x" * 4001, None, ["text"]])
def test_question_bounds_are_enforced(corpus, question):
    from rag_core.pipeline import RAGError, answer

    with pytest.raises(RAGError) as caught:
        answer(question)
    assert caught.value.code == "invalid_question"


@pytest.mark.parametrize("question", ["\ud800", "\udfff", "returns \ud800 please"])
def test_unpaired_surrogates_are_rejected_before_corpus_or_provider_access(corpus, monkeypatch, question):
    from rag_core import pipeline, providers

    monkeypatch.setenv("RAG_BACKEND", "openai")
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid Unicode must be rejected before retrieval or provider access")
    monkeypatch.setattr(pipeline, "_corpus", forbidden)
    monkeypatch.setattr(providers, "make_embeddings", forbidden)
    monkeypatch.setattr(providers, "generate_answer", forbidden)
    with pytest.raises(pipeline.RAGError) as caught:
        pipeline.answer(question)
    assert caught.value.code == "invalid_question"


def test_invalid_unicode_history_is_skipped_and_cannot_reach_retrieval(corpus):
    from rag_core import providers
    from rag_core.pipeline import answer

    history = [
        {"role": "user", "content": "退货政策"},
        {"role": "assistant", "content": "Valid reply"},
        {"role": "user", "content": "broken \ud800 history"},
        {"role": "assistant", "content": "broken \udfff history"},
    ]
    assert providers.safe_history(history) == history[:2]
    result = answer("那多久呢？", history=history)
    assert result["retrieval_query"] == "退货政策 那多久呢？"
    assert result["retrieval_query"].encode("utf-8")


def test_history_with_invalid_unicode_beyond_limit_is_skipped():
    from rag_core.providers import safe_history

    history = [{"role": "user", "content": "valid prefix" + "x" * 2000 + "\ud800"}]
    assert safe_history(history, max_chars=20) == []


def test_followup_heuristic_only_uses_prior_user_message(corpus):
    from rag_core.pipeline import answer

    history = [{"role": "user", "content": "退货政策"}, {"role": "assistant", "content": "assistant-should-not-be-a-query"}]
    result = answer("那多久呢？", history=history)
    assert result["retrieval_query"] == "退货政策 那多久呢？"
    assert "assistant-should-not-be-a-query" not in result["retrieval_query"]
    assert result["grounded"]


def test_openai_mode_requires_configuration_and_never_falls_back(corpus, monkeypatch):
    from rag_core.pipeline import RAGError, answer, build_index

    monkeypatch.setenv("RAG_BACKEND", "openai")
    monkeypatch.delenv("OPENAI_CHAT_MODEL", raising=False)
    with pytest.raises(RAGError) as caught:
        answer("returns")
    assert caught.value.code == "configuration_error"
    with pytest.raises(RAGError) as caught:
        build_index()
    assert caught.value.code == "configuration_error"


def test_provider_exception_is_redacted():
    from rag_core.config import load_config
    from rag_core import providers
    from rag_core.pipeline import RAGError
    from dataclasses import replace

    config = replace(load_config(), api_key="test-only-private-value-do-not-echo", chat_model="test-model")
    class BrokenChat:
        def __init__(self, **kwargs):
            pass
        def invoke(self, messages):
            raise RuntimeError("test-only-private-value-do-not-echo full provider trace")
    original_import = providers._import_langchain
    providers._import_langchain = lambda: (None, BrokenChat)
    try:
        with pytest.raises(RAGError) as caught:
            providers.generate_answer(config, "question", [], [])
        assert caught.value.code == "provider_error"
        assert "private-value" not in str(caught.value)
        assert "trace" not in caught.value.public_message
    finally:
        providers._import_langchain = original_import


def test_incompatible_optional_api_installation_is_a_public_error(monkeypatch):
    import builtins
    from rag_core import providers
    from rag_core.pipeline import RAGError

    original_import = builtins.__import__
    def incompatible(name, *args, **kwargs):
        if name == "langchain_openai":
            raise RuntimeError("dependency initialization leaked private details")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", incompatible)
    with pytest.raises(RAGError) as caught:
        providers._import_langchain()
    assert caught.value.code == "missing_dependency"
    assert "private details" not in str(caught.value)
