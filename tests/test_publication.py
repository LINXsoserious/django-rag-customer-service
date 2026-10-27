from pathlib import Path

import pytest

from scripts.check_publication import scan


def test_publication_rejects_secrets_without_printing_them(tmp_path):
    value = "sk-" + "a1B2c3D4" * 5
    (tmp_path / "bad.py").write_text('API_KEY = "' + value + '"\n', encoding="utf-8")
    findings = scan(tmp_path, ["bad.py"])
    assert findings
    assert value not in str(findings)
    assert all(item["path"] == "bad.py" for item in findings)


def test_publication_rejects_original_private_artifacts(tmp_path):
    for name in [".env", "db.sqlite3", "index.pkl", "document.pdf", "environment.zip"]:
        (tmp_path / name).write_bytes(b"not for publication")
    findings = scan(tmp_path, [".env", "db.sqlite3", "index.pkl", "document.pdf", "environment.zip"])
    assert len(findings) == 5
    assert {item["rule"] for item in findings} == {"excluded_artifact"}


def test_publication_accepts_empty_template_and_redacted_reference(tmp_path):
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    (tmp_path / "reference.py.txt").write_text('api_key = "<CONFIGURE_VIA_ENVIRONMENT>"\n', encoding="utf-8")
    assert scan(tmp_path, [".env.example", "reference.py.txt"]) == []


def test_publication_rejects_parent_traversal(tmp_path):
    assert scan(tmp_path, ["../outside.txt"])[0]["rule"] == "outside_publication_root"


@pytest.mark.parametrize("value", [
    "Py" + "thon" + "AI" + str(2099),
    "da" + "y" + str(73),
    "第" + str(73) + "课" + "时",
    chr(67) + ":" + chr(92) + "private" + chr(92) + "notes.txt",
    chr(92) * 2 + "server" + chr(92) + "share" + chr(92) + "notes.txt",
    "_".join(("training", "demo")),
], ids=["private-label", "numbered-label", "numbered-heading", "drive-location", "network-location", "legacy-name"])
def test_publication_rejects_private_context_without_echoing_it(tmp_path, value):
    (tmp_path / "sample.txt").write_text(value, encoding="utf-8")
    findings = scan(tmp_path, ["sample.txt"])
    assert findings
    assert value not in str(findings)
    assert findings[0]["rule"] in {"private_identifier", "numbered_teaching_label", "local_path"}


def test_publication_keeps_business_durations_and_service_urls(tmp_path):
    (tmp_path / "policy.txt").write_text("Returns within 14 days. https://api.openai.com/v1", encoding="utf-8")
    assert scan(tmp_path, ["policy.txt"]) == []
