"""Verified JSON/FAISS bundles. FAISS is optional and no pickle is read."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .documents import Chunk, chunks_from_json
from .errors import RAGError

SCHEMA_VERSION = 1
FILE_LIMITS = {"manifest.json": 64_000, "chunks.json": 25_000_000, "index.faiss": 512_000_000}


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_bundle(folder: str | Path, chunks: list[Chunk], *, backend: str,
                 corpus_sha256: str, embedding_model: str, document_count: int,
                 chunk_size: int, chunk_overlap: int, vector_bytes: bytes | None = None,
                 dimension: int | None = None) -> None:
    """Publish the manifest last, so partial writes are rejected on the next read."""
    path = Path(folder)
    payloads = {"chunks.json": _json_bytes([chunk.to_dict() for chunk in chunks])}
    if vector_bytes is not None:
        payloads["index.faiss"] = vector_bytes
    manifest = {
        "schema_version": SCHEMA_VERSION, "backend": backend, "corpus_sha256": corpus_sha256,
        "embedding_model": embedding_model, "document_count": document_count,
        "chunk_count": len(chunks), "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
        "dimension": dimension,
        "files": {name: hashlib.sha256(value).hexdigest() for name, value in payloads.items()},
    }
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".rag-build-", dir=path) as staging:
            staging_path = Path(staging)
            for name, value in payloads.items():
                (staging_path / name).write_bytes(value)
            (staging_path / "manifest.json").write_bytes(_json_bytes(manifest))
            for name in [*payloads, "manifest.json"]:
                os.replace(staging_path / name, path / name)
    except (OSError, TypeError, ValueError):
        raise RAGError("index_write_error", "The index could not be saved. Check the configured runtime folder.") from None


def _read_limited(path: Path, name: str) -> bytes:
    target = path / name
    if target.is_symlink() or not target.is_file() or target.stat().st_size > FILE_LIMITS[name]:
        raise RAGError("index_corrupt", "Index files are missing or invalid. Rebuild the index.")
    return target.read_bytes()


def read_bundle(folder: str | Path, *, backend: str, corpus_sha256: str,
                embedding_model: str, chunk_size: int, chunk_overlap: int) -> tuple[list[Chunk], dict, bytes | None]:
    path = Path(folder)
    if not (path / "manifest.json").exists():
        raise RAGError("index_missing", "No built index is available. Build the index before using API mode.")
    try:
        manifest = json.loads(_read_limited(path, "manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError
        expected_files = {"chunks.json", "index.faiss"} if manifest.get("backend") == "openai" else {"chunks.json"}
        files = manifest.get("files")
        if (manifest.get("backend") not in {"demo", "openai"} or not isinstance(files, dict)
                or set(files) != expected_files or any(not isinstance(v, str) or len(v) != 64 for v in files.values())
                or type(manifest.get("chunk_count")) is not int or manifest["chunk_count"] < 1
                or type(manifest.get("document_count")) is not int or manifest["document_count"] < 1):
            raise ValueError
        payloads = {name: _read_limited(path, name) for name in expected_files}
        if any(hashlib.sha256(payloads[name]).hexdigest() != digest for name, digest in files.items()):
            raise ValueError
        chunks = chunks_from_json(json.loads(payloads["chunks.json"]))
        if len(chunks) != manifest["chunk_count"]:
            raise ValueError
        expected = {"backend": backend, "corpus_sha256": corpus_sha256, "embedding_model": embedding_model,
                    "chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise RAGError("index_stale", "The corpus or retrieval configuration changed. Rebuild the index.")
        return chunks, manifest, payloads.get("index.faiss")
    except RAGError:
        raise
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        raise RAGError("index_corrupt", "The saved index is damaged or invalid. Rebuild the index.") from None


def _dependencies():
    try:
        import faiss
        import numpy as np
    except Exception:
        raise RAGError("missing_dependency", "FAISS dependencies are unavailable. Install the vector extra.") from None
    return faiss, np


def _matrix(values, expected_rows: int):
    _, np = _dependencies()
    try:
        array = np.ascontiguousarray(values, dtype=np.float32)
        if (array.ndim != 2 or array.shape[0] != expected_rows or array.shape[1] < 1
                or not np.isfinite(array).all() or (np.linalg.norm(array, axis=1) == 0).any()):
            raise ValueError
    except (TypeError, ValueError):
        raise RAGError("provider_error", "The embedding provider returned invalid vectors.") from None
    return array


class FaissIndex:
    def __init__(self, chunks: list[Chunk], embedder, index):
        self.chunks = list(chunks)
        self.embedder = embedder
        self.index = index

    @classmethod
    def build(cls, chunks: list[Chunk], embedder):
        faiss, _ = _dependencies()
        if not chunks:
            raise RAGError("empty_corpus", "The knowledge corpus contains no searchable text.")
        try:
            vectors = _matrix(embedder.embed_documents([chunk.text for chunk in chunks]), len(chunks))
            faiss.normalize_L2(vectors)
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
        except RAGError:
            raise
        except Exception:
            raise RAGError("provider_error", "Embedding generation failed. Check the API configuration and service.") from None
        return cls(chunks, embedder, index)

    def search(self, query: str, top_k: int = 4, min_score: float = 0.15) -> list[dict]:
        faiss, _ = _dependencies()
        count = min(max(top_k, 0), len(self.chunks))
        if not count:
            return []
        try:
            vector = _matrix([self.embedder.embed_query(query)], 1)
            if vector.shape[1] != self.index.d:
                raise RAGError("index_stale", "The embedding dimension changed. Rebuild the index.")
            faiss.normalize_L2(vector)
            scores, positions = self.index.search(vector, count)
        except RAGError:
            raise
        except Exception:
            raise RAGError("provider_error", "Query embedding generation failed. Check the API configuration and service.") from None
        return [self.chunks[int(position)].citation(float(score))
                for score, position in zip(scores[0], positions[0])
                if 0 <= position < len(self.chunks) and float(score) >= min_score]

    def save(self, folder: str | Path, *, corpus_sha256: str, embedding_model: str,
             document_count: int, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        faiss, _ = _dependencies()
        try:
            binary = faiss.serialize_index(self.index).tobytes()
        except Exception:
            raise RAGError("index_write_error", "The FAISS index could not be serialized.") from None
        write_bundle(folder, self.chunks, backend="openai", corpus_sha256=corpus_sha256,
                     embedding_model=embedding_model, document_count=document_count,
                     chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                     vector_bytes=binary, dimension=int(self.index.d))

    @classmethod
    def load(cls, folder: str | Path, embedder, *, corpus_sha256: str, embedding_model: str,
             chunk_size: int = 1000, chunk_overlap: int = 200):
        chunks, manifest, binary = read_bundle(folder, backend="openai", corpus_sha256=corpus_sha256,
                                               embedding_model=embedding_model,
                                               chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        faiss, np = _dependencies()
        try:
            if type(manifest.get("dimension")) is not int or manifest["dimension"] < 1 or binary is None:
                raise ValueError
            index = faiss.deserialize_index(np.frombuffer(binary, dtype=np.uint8))
            if (not isinstance(index, faiss.IndexFlatIP) or index.d != manifest["dimension"]
                    or index.ntotal != len(chunks) or index.metric_type != faiss.METRIC_INNER_PRODUCT):
                raise ValueError
        except Exception:
            raise RAGError("index_corrupt", "The FAISS index is damaged or inconsistent. Rebuild the index.") from None
        return cls(chunks, embedder, index)
