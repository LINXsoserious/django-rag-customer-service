from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone


@pytest.mark.django_db
def test_cleanup_defaults_to_dry_run_and_requires_apply():
    from chatbot_app.models import ChatSession

    old = ChatSession.objects.create(owner_key="old-browser")
    recent = ChatSession.objects.create(owner_key="recent-browser")
    ChatSession.objects.filter(pk=old.pk).update(updated_at=timezone.now() - timedelta(days=40))
    output = StringIO()
    call_command("cleanup_old_sessions", days=30, stdout=output)
    assert "dry-run" in output.getvalue().lower()
    assert ChatSession.objects.filter(pk=old.pk).exists()
    call_command("cleanup_old_sessions", days=30, apply=True, stdout=StringIO())
    assert not ChatSession.objects.filter(pk=old.pk).exists()
    assert ChatSession.objects.filter(pk=recent.pk).exists()
    with pytest.raises(CommandError):
        call_command("cleanup_old_sessions", days=0, stdout=StringIO())


def test_build_index_command_delegates_explicit_backend_and_folder(monkeypatch):
    calls = []

    def build(folder=None, backend=None):
        calls.append((folder, backend))
        return {"backend": backend, "document_count": 2, "chunk_count": 3,
                "index_path": ".runtime/index", "corpus_sha256": "a" * 64}

    monkeypatch.setattr("chatbot_app.management.commands.build_index.build_index_from_folder", build)
    call_command("build_index", backend="demo", folder="data/sample_docs", stdout=StringIO())
    call_command("build_faiss_index", backend="demo", stdout=StringIO())
    assert calls == [("data/sample_docs", "demo"), (None, "demo")]
