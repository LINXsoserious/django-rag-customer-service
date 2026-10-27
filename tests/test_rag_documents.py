"""Offline regressions for source spans and deterministic local retrieval."""

import json

import pytest


def test_chunks_really_overlap_and_citations_are_original_spans():
    from rag_core.documents import Document, chunk_documents

    text = "0123456789ABCDEFGHIJ中文最后"
    chunks = chunk_documents([Document(source="nested/policy.txt", text=text)], 10, 3)
    assert [(c.start, c.end) for c in chunks] == [(0, 10), (7, 17), (14, 24)]
    assert chunks[0].text[-3:] == chunks[1].text[:3]
    for chunk in chunks:
        assert chunk.text == text[chunk.start:chunk.end]
        assert chunk.source == "nested/policy.txt"
    assert len({c.chunk_id for c in chunks}) == len(chunks)


@pytest.mark.parametrize("size,overlap", [(0, 0), (4, 4), (4, -1)])
def test_invalid_chunk_settings_fail_clearly(size, overlap):
    from rag_core.documents import Document, chunk_documents
    from rag_core.errors import RAGError

    with pytest.raises(RAGError, match="chunk"):
        chunk_documents([Document("a.txt", "text")], size, overlap)


@pytest.mark.parametrize("source", ["/private.txt", chr(67) + ":" + "/private.txt", "../private.txt", "folder\\private.txt"])
def test_sources_cannot_disclose_absolute_or_escaping_paths(source):
    from rag_core.documents import Document, chunk_documents
    from rag_core.errors import RAGError

    with pytest.raises(RAGError):
        chunk_documents([Document(source, "private")], 20, 2)


def test_document_loader_preserves_exact_utf8_and_uses_relative_names(tmp_path):
    from rag_core.documents import corpus_sha256, load_documents

    nested = tmp_path / "nested"
    nested.mkdir()
    text = "退货政策\n第二行。\n"
    (nested / "policy.txt").write_text(text, encoding="utf-8", newline="")
    (tmp_path / "ignored.pdf").write_bytes(b"not a document")
    documents = load_documents(tmp_path)
    assert [(d.source, d.text) for d in documents] == [("nested/policy.txt", text)]
    first_hash = corpus_sha256(documents)
    (nested / "policy.txt").write_text(text + "更新", encoding="utf-8")
    assert corpus_sha256(load_documents(tmp_path)) != first_hash


def test_bilingual_lexical_retrieval_returns_real_ranked_citations():
    from rag_core.documents import Document, chunk_documents
    from rag_core.lexical import LexicalIndex

    docs = [Document("returns.txt", "退货政策：收货后七天内可申请退货。 Returns accepted within seven days."),
            Document("shipping.txt", "Shipping dispatch takes two business days. 物流发货需要两个工作日。")]
    index = LexicalIndex(chunk_documents(docs, 1000, 200))
    for question in ["退货政策", "returns"]:
        hits = index.search(question, top_k=4)
        assert hits[0]["source"] == "returns.txt"
        assert hits[0]["score"] > 0
        assert len(hits) <= len(docs)
        assert hits[0]["text"] == docs[0].text[hits[0]["start"]:hits[0]["end"]]
        json.dumps(hits, ensure_ascii=False)
    assert index.search("quantumbanana", top_k=4) == []
    assert index.search("the is and", top_k=4) == []
