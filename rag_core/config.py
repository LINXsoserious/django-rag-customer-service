"""Environment configuration usable by Django and independent examples."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .errors import RAGError


@dataclass(frozen=True)
class RAGConfig:
    root: Path
    docs_dir: Path
    index_dir: Path
    backend: str = "demo"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 4
    max_question_chars: int = 4000
    api_key: str = field(default="", repr=False)
    base_url: str = "https://api.openai.com/v1"
    chat_model: str = ""
    embedding_model: str = "text-embedding-3-small"
    request_timeout: float = 30.0
    min_vector_score: float = 0.15


def _integer(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        raise RAGError("configuration_error", f"{name} must be an integer.") from None
    if not low <= value <= high:
        raise RAGError("configuration_error", f"{name} is outside its supported range.")
    return value


def resolve_path(value: str | Path, root: Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def load_config(root: str | Path | None = None) -> RAGConfig:
    package_dir = Path(__file__).resolve().parent
    source_root = package_dir.parent
    source_checkout = (source_root / "pyproject.toml").is_file()
    if root is not None:
        root_path = Path(root).resolve()
        default_docs = root_path / "data" / "sample_docs"
    elif source_checkout:
        root_path = source_root
        default_docs = root_path / "data" / "sample_docs"
    else:
        # Installed packages may live in read-only site-packages. Keep private
        # configuration and generated indexes in the caller's working folder.
        root_path = Path.cwd().resolve()
        default_docs = package_dir / "sample_docs"
    # Explicit process environment always wins over the optional private .env.
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv(root_path / ".env", override=False)

    backend = os.environ.get("RAG_BACKEND", "demo").strip().lower()
    if backend not in {"demo", "openai"}:
        raise RAGError("configuration_error", "RAG_BACKEND must be demo or openai.")
    chunk_size = _integer("RAG_CHUNK_SIZE", 1000, 1, 100_000)
    overlap = _integer("RAG_CHUNK_OVERLAP", 200, 0, 99_999)
    if overlap >= chunk_size:
        raise RAGError("configuration_error", "RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE.")
    try:
        timeout = float(os.environ.get("RAG_REQUEST_TIMEOUT", "30"))
        minimum = float(os.environ.get("RAG_MIN_VECTOR_SCORE", "0.15"))
    except ValueError:
        raise RAGError("configuration_error", "RAG timeout and similarity threshold must be numbers.") from None
    if not 1 <= timeout <= 120 or not -1 <= minimum <= 1:
        raise RAGError("configuration_error", "RAG timeout or similarity threshold is outside its supported range.")

    return RAGConfig(
        root=root_path,
        docs_dir=resolve_path(os.environ.get("RAG_DOCS_DIR", default_docs), root_path),
        index_dir=resolve_path(os.environ.get("RAG_INDEX_DIR", ".runtime/index"), root_path),
        backend=backend,
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        top_k=_integer("RAG_TOP_K", 4, 1, 20),
        max_question_chars=_integer("RAG_MAX_QUESTION_CHARS", 4000, 1, 8000),
        api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        chat_model=os.environ.get("OPENAI_CHAT_MODEL", "").strip(),
        embedding_model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        request_timeout=timeout,
        min_vector_score=minimum,
    )


def require_api_configuration(config: RAGConfig) -> None:
    if not config.api_key or not config.chat_model or not config.embedding_model:
        raise RAGError("configuration_error", "API mode requires OPENAI_API_KEY, OPENAI_CHAT_MODEL and OPENAI_EMBEDDING_MODEL.")
    try:
        url = urlsplit(config.base_url)
        valid = (url.scheme == "https" or (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}))
        valid = valid and bool(url.hostname) and not (url.username or url.password or url.query or url.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise RAGError("configuration_error", "OPENAI_BASE_URL must be an HTTPS URL or a local HTTP service, without credentials or query parameters.")
