"""Build and test the actual wheel away from the repository, with network blocked.

Run explicitly with ``python scripts/check_wheel.py`` after installing build and
hatchling. This smoke is separate from the default unit suite.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_publication import DENIED_COMPONENTS, DENIED_SUFFIXES


SMOKE = r'''
import builtins
import json
import os
from pathlib import Path
import socket

def forbidden_network(*args, **kwargs):
    raise AssertionError("Installed demo attempted a network connection")
socket.create_connection = forbidden_network
socket.socket.connect = forbidden_network
socket.socket.connect_ex = forbidden_network
original_import = builtins.__import__
def no_optional_models(name, *args, **kwargs):
    if name.split(".")[0] in {"langchain_openai", "openai", "faiss", "torch", "sentence_transformers", "requests", "httpx"}:
        raise AssertionError("Installed demo imported optional model/API dependencies")
    return original_import(name, *args, **kwargs)
builtins.__import__ = no_optional_models

import rag_core
from rag_core.config import load_config
from rag_core.pipeline import RAGError, answer, build_index
site = Path(os.environ["WHEEL_SMOKE_SITE"]).resolve()
package = Path(rag_core.__file__).resolve().parent
assert package.is_relative_to(site), "Repository import leaked into wheel smoke"
config = load_config()
working = Path.cwd().resolve()
assert config.root.resolve() == working, f"runtime_root: configured={config.root!s}; cwd={working!s}"
assert config.docs_dir == package / "sample_docs", f"packaged_documents: configured={config.docs_dir!s}; package={package!s}"
assert config.index_dir.resolve() == working / ".runtime" / "index", f"runtime_index: configured={config.index_dir!s}; cwd={working!s}"
result = answer("returns", lang="en")
assert result["mode"] == "extractive_demo" and result["grounded"], "default_answer: expected grounded extractive_demo"
assert any(item["source"] == "returns.txt" and "return" in item["text"].lower() for item in result["sources"]), "default_citations: returns.txt evidence missing"
built = build_index()
assert Path(built["index_path"]) == config.index_dir, "built_index_path: unexpected runtime location"
assert (config.index_dir / "manifest.json").is_file(), "built_manifest: missing manifest.json"
assert answer("returns", lang="en")["grounded"], "persisted_answer: evidence missing after building index"
os.environ["RAG_DOCS_DIR"] = "explicitly-missing-documents"
try:
    answer("returns")
except RAGError as exc:
    assert exc.code == "invalid_corpus", f"explicit_missing_documents: unexpected error code {exc.code}"
else:
    raise AssertionError("Explicit missing document configuration was silently replaced")
print(json.dumps({"isolated_import": True, "sources": [item["source"] for item in result["sources"]], "network": "blocked"}))
'''


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="rag-wheel-") as temporary:
        workspace = Path(temporary)
        distribution = workspace / "dist"
        run_checked([sys.executable, "-m", "build", "--sdist", "--wheel", "--no-isolation", "--outdir", str(distribution)],
                    stage="build distributions", cwd=root)
        wheels = list(distribution.glob("*.whl"))
        source_archives = list(distribution.glob("*.tar.gz"))
        if len(wheels) != 1 or len(source_archives) != 1:
            raise RuntimeError("Expected exactly one built wheel and source archive")
        site = workspace / "site"
        with zipfile.ZipFile(wheels[0]) as wheel:
            assert "rag_core/sample_docs/returns.txt" in wheel.namelist(), "Wheel is missing the sample corpus"
            check_members(wheel.namelist())
            wheel.extractall(site)
        with tarfile.open(source_archives[0]) as source:
            check_members([str(Path(*Path(item.name).parts[1:])) for item in source.getmembers() if item.isfile()])
        working = workspace / "working"
        working.mkdir()
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("RAG_", "OPENAI_", "DJANGO_"))}
        env.update(PYTHONPATH=str(site), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
                   WHEEL_SMOKE_SITE=str(site), RAG_BACKEND="demo")
        locations = [("native", working)]
        short_working = windows_short_path(working)
        if short_working is not None and str(short_working) != str(working):
            locations.append(("windows_short_path", short_working))
        outcomes = []
        for mode, location in locations:
            result = run_checked([sys.executable, "-c", SMOKE], stage=f"isolated installed-wheel smoke ({mode})",
                                 cwd=location, env=env)
            outcomes.append(json.loads(result.stdout.decode("utf-8")))
        print(json.dumps({"verified_artifacts": [source_archives[0].name, wheels[0].name],
                          "smoke": outcomes[0], "cwd_checks": [mode for mode, _ in locations]}, ensure_ascii=False))
    return 0


def run_checked(command: list[str], *, stage: str, cwd: Path, env=None):
    """Keep the original subprocess failure visible instead of losing its stderr."""
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True)
    if result.returncode:
        print(f"Wheel check failed during {stage} (exit {result.returncode}).", file=sys.stderr)
        for label, value in (("stdout", result.stdout), ("stderr", result.stderr)):
            if value:
                print(f"--- subprocess {label} ---", file=sys.stderr)
                print(value.decode("utf-8", errors="backslashreplace"), file=sys.stderr)
        raise RuntimeError(f"Wheel check failed during {stage}; see subprocess output above.")
    return result


def windows_short_path(path: Path) -> Path | None:
    """Exercise the runner's 8.3 aliases when the filesystem provides them."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    get_short_path = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
    get_short_path.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    get_short_path.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_short_path(str(path), buffer, len(buffer))
    return Path(buffer.value) if 0 < length < len(buffer) else None


def check_members(names: list[str]) -> None:
    """Apply the publication artifact exclusions to both built distributions."""
    for name in names:
        member = Path(name)
        excluded_env = member.name == ".env" or (member.name.startswith(".env.") and member.name != ".env.example")
        if (member.is_absolute() or ".." in member.parts or set(member.parts) & DENIED_COMPONENTS
                or member.suffix.lower() in DENIED_SUFFIXES or excluded_env or member.name == "your_env"):
            raise AssertionError(f"Excluded artifact in built distribution: {name}")


if __name__ == "__main__":
    raise SystemExit(main())
