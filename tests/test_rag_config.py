"""Installed wheels use packaged evidence and a writable caller-owned runtime."""

import pytest


@pytest.fixture
def installed_package(tmp_path, monkeypatch):
    from rag_core import config

    package = tmp_path / "site" / "rag_core"
    documents = package / "sample_docs"
    documents.mkdir(parents=True)
    (documents / "returns.txt").write_text("Returns within seven days", encoding="utf-8")
    working = tmp_path / "working"
    working.mkdir()
    monkeypatch.chdir(working)
    monkeypatch.setattr(config, "__file__", str(package / "config.py"))
    monkeypatch.delenv("RAG_DOCS_DIR", raising=False)
    monkeypatch.delenv("RAG_INDEX_DIR", raising=False)
    monkeypatch.setenv("RAG_BACKEND", "demo")
    return package, working


def test_installed_package_uses_bundled_docs_and_cwd_runtime(installed_package):
    from rag_core.config import load_config

    package, working = installed_package
    config = load_config()
    assert config.root == working
    assert config.docs_dir == package / "sample_docs"
    assert config.index_dir == working / ".runtime" / "index"


def test_explicit_root_does_not_fall_back_to_packaged_documents(installed_package):
    from rag_core.config import load_config
    from rag_core.documents import load_documents
    from rag_core.errors import RAGError

    _, working = installed_package
    explicit = working / "custom"
    config = load_config(root=explicit)
    assert config.root == explicit
    assert config.docs_dir == explicit / "data" / "sample_docs"
    with pytest.raises(RAGError) as caught:
        load_documents(config.docs_dir)
    assert caught.value.code == "invalid_corpus"


def test_explicit_document_environment_does_not_fall_back(installed_package, monkeypatch):
    from rag_core.config import load_config
    from rag_core.documents import load_documents
    from rag_core.errors import RAGError

    _, working = installed_package
    monkeypatch.setenv("RAG_DOCS_DIR", "missing-user-corpus")
    config = load_config()
    assert config.docs_dir == working / "missing-user-corpus"
    with pytest.raises(RAGError) as caught:
        load_documents(config.docs_dir)
    assert caught.value.code == "invalid_corpus"
