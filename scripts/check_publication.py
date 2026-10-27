"""Check the publication set without printing matched credential values."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import subprocess

DENIED_COMPONENTS = {".git", ".idea", ".venv", "venv", "site-packages", "__pycache__", ".runtime", "faiss_index", "chroma_db", "models"}
DENIED_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pkl", ".pickle", ".faiss", ".pyc", ".zip", ".pt", ".pth", ".safetensors", ".pdf", ".docx", ".xmind"}
CREDENTIAL = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{25,}|ghp_[A-Za-z0-9]{25,}|hf_[A-Za-z0-9]{25,}|gsk_[A-Za-z0-9_-]{25,})\b")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
LITERAL_SECRET = re.compile(r"(?im)(?:api[_-]?key|secret[_-]?key|password|access[_-]?token)\s*[\"']?\s*[:=]\s*([\"'])([^\"'\r\n]{12,})\1")
PLACEHOLDER = re.compile(r"placeholder|redact|configure|example|for.testing|test.only|test-secret|ci-only|your[_ -]", re.I)
PRIVATE_CONTEXT = re.compile("|".join((
    r"python\s*ai\s*20\d{2}",
    r"(?:course|lesson|training)[_-](?:rag|demo)",
)), re.I)
NUMBERED_TEACHING_LABEL = re.compile(
    r"(?<![A-Za-z])da[y]\s*[-_ ]?\s*\d{1,3}(?!\d)|第\s*[一二三四五六七八九十百零〇\d]+\s*(?:课(?:时)?|讲|节(?:课)?|天)", re.I)
_SLASH = re.escape(chr(92))
LOCAL_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|" + _SLASH + r"{2,4}[A-Za-z0-9][A-Za-z0-9._-]+"
    + _SLASH + r"{1,2}[A-Za-z0-9$][A-Za-z0-9$._-]+", re.I)
PRIVACY_RULES = (("private_identifier", PRIVATE_CONTEXT),
                 ("numbered_teaching_label", NUMBERED_TEACHING_LABEL), ("local_path", LOCAL_PATH))


def publication_paths(root: Path) -> list[str]:
    if (root / ".git").exists():
        result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                                cwd=root, capture_output=True, check=True)
        return sorted(set(name for name in result.stdout.decode("utf-8").split("\0") if name))
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
                  and not set(path.relative_to(root).parts) & DENIED_COMPONENTS)


def scan(root: Path, paths: list[str] | None = None) -> list[dict]:
    root = root.resolve()
    findings = []
    for name in paths if paths is not None else publication_paths(root):
        relative = PurePosixPath(name.replace("\\", "/"))
        path = root / Path(relative)
        for rule, pattern in PRIVACY_RULES:
            if pattern.search(str(relative)):
                findings.append({"path": str(relative), "rule": rule})
        if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(root):
            findings.append({"path": str(relative), "rule": "outside_publication_root"})
            continue
        if (set(relative.parts) & DENIED_COMPONENTS or relative.suffix.lower() in DENIED_SUFFIXES
                or relative.name in {".env", "your_env"} or (relative.name.startswith(".env.") and relative.name != ".env.example")):
            findings.append({"path": str(relative), "rule": "excluded_artifact"})
            continue
        if not path.is_file():
            findings.append({"path": str(relative), "rule": "missing_file"})
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            findings.append({"path": str(relative), "rule": "unexpected_large_file"})
            continue
        if relative.suffix.lower() in {".png", ".jpg", ".jpeg", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            findings.append({"path": str(relative), "rule": "unexpected_binary_or_encoding"})
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for rule, pattern in PRIVACY_RULES:
                if pattern.search(line):
                    findings.append({"path": str(relative), "line": number, "rule": rule})
            if CREDENTIAL.search(line) or PRIVATE_KEY.search(line):
                findings.append({"path": str(relative), "line": number, "rule": "credential_pattern"})
            for matched in LITERAL_SECRET.finditer(line):
                if not PLACEHOLDER.search(matched.group(2)):
                    findings.append({"path": str(relative), "line": number, "rule": "literal_secret"})
        if relative.suffix.lower() == ".ipynb":
            try:
                notebook = json.loads(text)
            except ValueError:
                findings.append({"path": str(relative), "rule": "invalid_notebook"})
            else:
                if any(cell.get("outputs") or cell.get("execution_count") is not None for cell in notebook.get("cells", [])):
                    findings.append({"path": str(relative), "rule": "notebook_output_or_execution_state"})
    return findings


def main():
    root = Path(__file__).resolve().parents[1]
    paths = publication_paths(root)
    findings = scan(root, paths)
    print(json.dumps({"checked_files": len(paths), "findings": findings}, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
