"""CLI output must remain valid UTF-8 on legacy Windows terminal encodings."""

import json
import os
from pathlib import Path
import subprocess
import sys


def test_manual_rag_prints_utf8_json_with_real_chinese_sources_under_cp1252():
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    process = subprocess.run(
        [sys.executable, "-m", "examples.manual_rag", "--question", "returns policy"],
        cwd=root, env=env, capture_output=True,
    )
    assert process.returncode == 0, process.stderr.decode("utf-8", errors="replace")
    result = json.loads(process.stdout.decode("utf-8"))
    assert result["question"] == "returns policy"
    assert result["mode"] == "retrieval_only_demo"
    assert result["generation_calls"] == 0
    assert result["sources"]
    source = result["sources"][0]
    assert source["source"] == "demo/returns.txt"
    assert "虚构NovaShop支持签收后14天内退货。" in source["text"]
    assert source["start"] == 0
    assert source["end"] == len(source["text"])
    assert source["score"] > 0
