# Validation record / 验证记录

This record describes local integration checks and their limits.

## Executed checks / 已执行验证

- Python 3.12.3, Django 5.2.18, python-dotenv 1.2.4; optional FAISS 1.15.1 and langchain-openai 1.7.2 installed for offline integration tests.
- `python -m pytest -q`: offline regressions cover exact chunk spans/overlap, lexical retrieval/no-evidence results, real FAISS persistence using local test embeddings, stale/corrupt index rejection, mocked provider errors, Unicode limits, CSRF, browser ownership and session CRUD/export. A subprocess regression confirms UTF-8 JSON and Chinese evidence even when the terminal defaults to cp1252.
- `python manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. A fresh local database migrated successfully.
- `python manage.py build_index --backend demo`: three fictional documents indexed. `python -m examples.manual_rag --question "returns policy"`: actual return-policy source and zero generation calls.
- `python scripts/check_publication.py`: no findings in the publication set. The check rejects private runtime artifacts, credential patterns, raw notebook outputs and unexpected large/binary files; this is a bounded scan, not a guarantee that every possible secret format is detectable.
- `python scripts/check_wheel.py`: built and inspected source/wheel distributions; isolated wheel import from a different working directory returned `returns.txt` evidence. Native and Windows 8.3 short-path working directories both passed after canonical path comparison. Network connections and optional model/API imports were blocked. Generated indexes stayed in the caller's working directory. Explicit missing document configuration failed instead of falling back silently.
- PowerShell launcher first-run flow completed: created a new virtual environment, installed base dependencies, migrated the database, built the demo index and served a successful health response. Three browser JavaScript fragments passed Node syntax checks; both templates rendered with debug disabled.
- Browser: Chinese question and actual source cards; English question; language change preserving conversation, unfinished draft, source selection and contact checkbox; history restore; JSON download with four messages and source metadata. Delete confirmation was opened and canceled; actual cascading deletion and ownership restrictions are covered by offline Django tests.

## Boundaries / 验证边界

No real embedding/chat provider request, model download, email or SMS was executed. Optional provider tests use mocks; they do not establish live API compatibility or generated-answer quality. Default output is explicitly extractive and performs local retrieval without an LLM.

GitHub Actions repeats checks on Ubuntu and Windows. The repository's Actions page is the current source for the exact commit's remote result; this local record does not predeclare a remote CI success.

离线测试覆盖检索、索引、会话隔离和接口校验，浏览器验证中英界面、真实引用、会话恢复和 JSON 导出。Windows 便捷脚本首次安装及启动流程已跑通；命令行在 cp1252 环境下的中文 JSON 输出也有回归验证。安装包在仓库外、阻断网络的环境中能检索示例知识。没有调用真实模型 API。GitHub 远端检查结果以对应提交的 Actions 状态为准。
