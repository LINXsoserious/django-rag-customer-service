"""UTF-8 corpus loading and exact character-span chunks; no model imports."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import RAGError

MAX_FILE_BYTES = 2_000_000
MAX_CORPUS_BYTES = 10_000_000
MAX_DOCUMENTS = 1000
MAX_CHUNKS = 50_000


@dataclass(frozen=True)
class Document:
    source: str
    text: str


@dataclass(frozen=True)
class Chunk:
    source: str
    chunk_id: str
    start: int
    end: int
    text: str

    def citation(self, score: float) -> dict:
        return {"source": self.source, "chunk_id": self.chunk_id, "start": self.start,
                "end": self.end, "text": self.text, "score": round(float(score), 6)}

    def to_dict(self) -> dict:
        return {"source": self.source, "chunk_id": self.chunk_id, "start": self.start,
                "end": self.end, "text": self.text}


def validate_source(source: str) -> None:
    if (not isinstance(source, str) or not source or "\\" in source or ":" in source
            or any(ord(c) < 32 for c in source) or PurePosixPath(source).is_absolute()
            or any(p in {"", ".", ".."} for p in source.split("/"))):
        raise RAGError("invalid_corpus", "Document sources must be safe relative paths.")


def load_documents(folder: str | Path) -> list[Document]:
    root = Path(folder).resolve()
    if not root.is_dir():
        raise RAGError("invalid_corpus", "The configured document folder is not available.")
    documents = []
    total_bytes = 0
    try:
        files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md"})
        if len(files) > MAX_DOCUMENTS:
            raise RAGError("invalid_corpus", "The document corpus contains too many files.")
        for path in files:
            # Avoid following either a file link or a linked ancestor outside the corpus.
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RAGError("invalid_corpus", "Linked documents outside the corpus are not supported.")
            source = path.relative_to(root).as_posix()
            validate_source(source)
            size = path.stat().st_size
            total_bytes += size
            if size > MAX_FILE_BYTES or total_bytes > MAX_CORPUS_BYTES:
                raise RAGError("invalid_corpus", "The document corpus exceeds the supported size.")
            text = path.read_bytes().decode("utf-8-sig")
            documents.append(Document(source, text))
    except (OSError, UnicodeError):
        raise RAGError("invalid_corpus", "Documents must be readable UTF-8 text files.") from None
    return documents


def corpus_sha256(documents: list[Document]) -> str:
    digest = hashlib.sha256()
    for document in sorted(documents, key=lambda d: d.source):
        for value in (document.source, document.text):
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def chunk_documents(documents: list[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> list[Chunk]:
    if (type(chunk_size) is not int or type(chunk_overlap) is not int or chunk_size < 1
            or not 0 <= chunk_overlap < chunk_size):
        raise RAGError("configuration_error", "Invalid chunk size or chunk overlap.")
    chunks = []
    sources = set()
    for document in documents:
        validate_source(document.source)
        if not isinstance(document.text, str) or document.source in sources:
            raise RAGError("invalid_corpus", "Each document requires text and a unique relative source.")
        sources.add(document.source)
        start = 0
        while start < len(document.text):
            end = min(start + chunk_size, len(document.text))
            text = document.text[start:end]
            if text.strip():
                chunk_id = hashlib.sha256(f"{document.source}\0{start}\0{end}".encode()).hexdigest()[:20]
                chunks.append(Chunk(document.source, chunk_id, start, end, text))
                if len(chunks) > MAX_CHUNKS:
                    raise RAGError("invalid_corpus", "The document corpus creates too many chunks.")
            if end == len(document.text):
                break
            start = end - chunk_overlap
    return chunks


def chunks_from_json(values: object) -> list[Chunk]:
    if not isinstance(values, list) or len(values) > MAX_CHUNKS:
        raise RAGError("index_corrupt", "Index metadata is invalid. Rebuild the index.")
    chunks = []
    identifiers = set()
    for value in values:
        try:
            if not isinstance(value, dict) or set(value) != {"source", "chunk_id", "start", "end", "text"}:
                raise ValueError
            chunk = Chunk(**value)
            validate_source(chunk.source)
            if (type(chunk.start) is not int or type(chunk.end) is not int or chunk.start < 0
                    or chunk.end <= chunk.start or not isinstance(chunk.text, str)
                    or chunk.end - chunk.start != len(chunk.text)
                    or not isinstance(chunk.chunk_id, str) or not re.fullmatch(r"[a-f0-9]{20}", chunk.chunk_id)
                    or chunk.chunk_id in identifiers):
                raise ValueError
        except (TypeError, ValueError, RAGError):
            raise RAGError("index_corrupt", "Index metadata is invalid. Rebuild the index.") from None
        chunks.append(chunk)
        identifiers.add(chunk.chunk_id)
    return chunks
