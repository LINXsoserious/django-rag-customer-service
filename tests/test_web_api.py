"""HTTP regression tests: no network or model provider is needed."""
import importlib.util
import json
import uuid

import pytest
from django.test import Client, override_settings


def test_web_implementation_modules_exist():
    for name in ("chatbot_app.models", "chatbot_app.views", "chatbot_app.urls"):
        assert importlib.util.find_spec(name) is not None, f"Missing web module: {name}"


@pytest.fixture
def pipeline(monkeypatch):
    calls = []

    def answer(question, chat_history=None, lang="zh"):
        calls.append((question, chat_history, lang))
        return {
            "answer": "Support is available on weekdays.",
            "sources": [{"source": "support.txt", "chunk_id": "support:0", "start": 0,
                         "end": 7, "text": "Support", "score": 0.75}],
            "mode": "extractive_demo", "retrieval_query": question, "grounded": True,
        }

    monkeypatch.setattr("chatbot_app.views.answer_with_rag", answer)
    return calls


def post(client, payload, **kwargs):
    return client.post("/api/chat/", data=json.dumps(payload), content_type="application/json", **kwargs)


@pytest.mark.django_db
def test_chat_success_persists_real_sources_and_server_owned_session(client, pipeline):
    from chatbot_app.models import ChatMessage, ChatSession

    response = post(client, {"message": "support", "user": "pretend-admin", "lang": "en"})
    assert response.status_code == 200
    data = response.json()
    session = ChatSession.objects.get(session_id=data["session_id"])
    assert session.owner_key == client.session.session_key
    assert session.user == "anonymous"
    assert session.messages.count() == 2
    reply = ChatMessage.objects.get(session=session, role="assistant")
    assert reply.sources == data["sources"]
    assert reply.mode == "extractive_demo"
    assert data["sources"][0]["source"] == "support.txt"
    assert data["contact_recorded"] is False
    assert data["feedback_recorded"] is False
    assert pipeline == [("support", [], "en")]


@pytest.mark.django_db
def test_history_only_uses_latest_ten_messages(client, pipeline):
    first = post(client, {"message": "start"}).json()
    from chatbot_app.models import ChatMessage, ChatSession

    session = ChatSession.objects.get(session_id=first["session_id"])
    for number in range(12):
        ChatMessage.objects.create(session=session, role="user", content=f"older {number}")
    assert post(client, {"message": "follow up", "session_id": first["session_id"]}).status_code == 200
    assert [item["content"] for item in pipeline[-1][1]] == [f"older {n}" for n in range(2, 12)]


@pytest.mark.django_db
def test_separate_browser_cannot_list_read_export_delete_or_continue_session(client, pipeline):
    session_id = post(client, {"message": "support"}).json()["session_id"]
    stranger = Client()
    assert stranger.get("/api/sessions/").json()["sessions"] == []
    for suffix in ("/", "/export/"):
        response = stranger.get(f"/api/sessions/{session_id}{suffix}")
        assert response.status_code == 404
    assert stranger.delete(f"/api/sessions/{session_id}/").status_code == 404
    assert post(stranger, {"message": "support", "session_id": session_id}).status_code == 404
    assert client.get(f"/api/sessions/{session_id}/").status_code == 200


@pytest.mark.django_db
def test_owned_session_read_export_delete_and_cascade(client, pipeline):
    session_id = post(client, {"message": "support"}).json()["session_id"]
    listing = client.get("/api/sessions/").json()["sessions"]
    assert [item["session_id"] for item in listing] == [session_id]
    detail = client.get(f"/api/sessions/{session_id}/").json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][1]["sources"][0]["source"] == "support.txt"
    export = client.get(f"/api/sessions/{session_id}/export/")
    assert export.status_code == 200
    assert "attachment;" in export.headers["Content-Disposition"]
    assert export.json()["session_id"] == session_id
    assert client.delete(f"/api/sessions/{session_id}/").status_code == 200
    from chatbot_app.models import ChatMessage, ChatSession
    assert not ChatSession.objects.exists()
    assert not ChatMessage.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["not-a-uuid", 123, "", False])
def test_invalid_chat_uuid_is_400(client, pipeline, value):
    response = post(client, {"message": "support", "session_id": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_session_id"


@pytest.mark.django_db
def test_unknown_chat_uuid_is_404_without_empty_session(client, pipeline):
    response = post(client, {"message": "support", "session_id": str(uuid.uuid4())})
    assert response.status_code == 404
    from chatbot_app.models import ChatSession
    assert not ChatSession.objects.exists()
    assert not pipeline


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [[], None, "text", {"message": ""}, {"message": " "},
                                    {"message": 12}, {"message": "x" * 4001},
                                    {"message": "support", "lang": "fr"},
                                    {"message": "support", "store_contact": "true"}])
def test_invalid_chat_shape_and_fields_are_400(client, pipeline, payload):
    response = post(client, payload)
    assert response.status_code == 400
    assert set(response.json()) == {"error"}
    assert not pipeline


@pytest.mark.django_db
def test_invalid_utf8_json_and_large_body_are_rejected(client, pipeline):
    for body in (b"{", b'"\xff"'):
        response = client.post("/api/chat/", data=body, content_type="application/json")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_json"
    response = client.post("/api/chat/", data=b" " * (32768 + 1), content_type="application/json")
    assert response.status_code == 413
    assert not pipeline


@pytest.mark.django_db
def test_excessively_nested_json_is_a_client_error(client, pipeline):
    body = '{"message":' + '[' * 10000 + '"support"' + ']' * 10000 + '}'
    response = client.post("/api/chat/", data=body, content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_json"
    assert not pipeline


@pytest.mark.django_db
def test_json_integer_over_python_digit_limit_is_a_client_error(client, pipeline):
    body = '{"message":"support","extra":' + "7" * 5000 + "}"
    response = client.post("/api/chat/", data=body, content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_json"
    assert not pipeline


@pytest.mark.django_db
def test_unpaired_unicode_surrogate_is_rejected_without_records(client, pipeline):
    response = post(client, {"message": "support\ud800"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_message"
    from chatbot_app.models import ChatMessage, ChatSession
    assert not ChatSession.objects.exists()
    assert not ChatMessage.objects.exists()
    assert not pipeline


@pytest.mark.django_db
def test_default_question_limit_accepts_2001_characters(client, monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "support.txt").write_text("Support is available on weekdays.", encoding="utf-8")
    monkeypatch.setenv("RAG_BACKEND", "demo")
    monkeypatch.delenv("RAG_MAX_QUESTION_CHARS", raising=False)
    monkeypatch.setenv("RAG_DOCS_DIR", str(docs))
    monkeypatch.setenv("RAG_INDEX_DIR", str(tmp_path / "index"))
    response = post(client, {"message": "x" * 2001})
    assert response.status_code == 200
    assert response.json()["mode"] == "extractive_demo"


@pytest.mark.django_db
def test_web_limit_follows_smaller_configured_limit(client, pipeline, monkeypatch):
    monkeypatch.setenv("RAG_MAX_QUESTION_CHARS", "200")
    response = post(client, {"message": "x" * 201})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_message"
    assert "200" in response.json()["error"]["message"]
    assert not pipeline


@pytest.mark.django_db
def test_web_limit_follows_larger_configured_limit(client, pipeline, monkeypatch):
    monkeypatch.setenv("RAG_MAX_QUESTION_CHARS", "5000")
    response = post(client, {"message": "x" * 4500})
    assert response.status_code == 200
    assert len(pipeline[0][0]) == 4500


@pytest.mark.django_db
def test_core_invalid_question_is_a_client_error(client, monkeypatch):
    from rag_core.errors import RAGError

    def reject(*args, **kwargs):
        raise RAGError("invalid_question", "Question exceeds the configured limit.")

    monkeypatch.setattr("chatbot_app.views.answer_with_rag", reject)
    response = post(client, {"message": "support"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_question"


@pytest.mark.django_db
def test_pipeline_failure_leaves_no_messages_contacts_feedback_or_empty_session(client, monkeypatch):
    from rag_core.errors import RAGError
    from chatbot_app.models import ChatMessage, ChatSession, Contact, NegativeFeedback

    def fail(*args, **kwargs):
        raise RAGError("provider_unavailable", "The provider is unavailable.")

    monkeypatch.setattr("chatbot_app.views.answer_with_rag", fail)
    response = post(client, {"message": "投诉 contact@example.test 13800138000", "store_contact": True})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert not any(model.objects.exists() for model in (ChatSession, ChatMessage, Contact, NegativeFeedback))


@pytest.mark.django_db
def test_existing_session_is_unchanged_after_unexpected_provider_failure(client, pipeline, monkeypatch):
    from chatbot_app.models import ChatSession

    session_id = post(client, {"message": "support"}).json()["session_id"]
    session = ChatSession.objects.get(session_id=session_id)
    previous_timestamp = session.updated_at

    def fail(*args, **kwargs):
        raise RuntimeError("private provider diagnostic must not reach the browser")

    monkeypatch.setattr("chatbot_app.views.answer_with_rag", fail)
    response = post(client, {"message": "follow up", "session_id": session_id})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "rag_unavailable"
    assert "private provider" not in response.content.decode()
    session.refresh_from_db()
    assert session.messages.count() == 2
    assert session.updated_at == previous_timestamp


@pytest.mark.django_db
def test_contact_capture_is_explicit_opt_in_and_feedback_is_heuristic(client, pipeline):
    from chatbot_app.models import Contact, NegativeFeedback

    message = "投诉 contact@example.test 13800138000"
    assert post(client, {"message": message}).json()["contact_recorded"] is False
    assert not Contact.objects.exists()
    response = post(client, {"message": message, "store_contact": True})
    assert response.json()["contact_recorded"] is True
    assert response.json()["feedback_recorded"] is True
    assert set(Contact.objects.values_list("contact_type", "contact_value")) == {
        ("email", "contact@example.test"), ("phone", "13800138000")}
    assert "13800138000" not in str(Contact.objects.first())
    assert all("keyword" in reason.lower() for reason in NegativeFeedback.objects.values_list("reason", flat=True))


TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": False,
              "OPTIONS": {"loaders": [("django.template.loaders.locmem.Loader", {
                  "chat.html": "{{ backend }} {{ app_version }}",
                  "sessions.html": "{% for session in sessions %}{{ session.session_id }}{% endfor %}",
              })]}}]


@pytest.mark.django_db
@override_settings(TEMPLATES=TEMPLATES)
def test_real_csrf_protection_for_post_and_delete(pipeline):
    browser = Client(enforce_csrf_checks=True)
    assert post(browser, {"message": "support"}).status_code == 403
    assert browser.get("/").status_code == 200
    token = browser.cookies["csrftoken"].value
    response = post(browser, {"message": "support"}, HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200
    url = f'/api/sessions/{response.json()["session_id"]}/'
    assert browser.delete(url).status_code == 403
    assert browser.delete(url, HTTP_X_CSRFTOKEN=token).status_code == 200


@pytest.mark.django_db
@override_settings(TEMPLATES=TEMPLATES)
def test_history_page_only_renders_current_browser_sessions(client, pipeline):
    session_id = post(client, {"message": "support"}).json()["session_id"]
    assert session_id in client.get("/sessions/").content.decode()
    assert session_id not in Client().get("/sessions/").content.decode()


@pytest.mark.django_db
@override_settings(TEMPLATES=TEMPLATES)
def test_direct_history_page_sets_csrf_cookie():
    browser = Client(enforce_csrf_checks=True)
    assert browser.get("/sessions/").status_code == 200
    assert "csrftoken" in browser.cookies


@pytest.mark.django_db
@override_settings(TEMPLATES=TEMPLATES)
def test_page_context_exposes_configured_question_limit(client, monkeypatch):
    monkeypatch.setenv("RAG_MAX_QUESTION_CHARS", "123")
    for path in ("/", "/sessions/"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.context["max_question_chars"] == 123


@pytest.mark.django_db
@override_settings(TEMPLATES=TEMPLATES)
def test_ui_and_health_use_normalized_backend(client, monkeypatch):
    monkeypatch.setenv("RAG_BACKEND", " OPENAI ")
    assert client.get("/").context["backend"] == "openai"
    assert client.get("/api/health/").json()["backend"] == "openai"


@pytest.mark.django_db
def test_admin_requires_staff_and_model_permissions(client, django_user_model):
    assert client.get("/admin/chatbot_app/contact/").status_code == 302
    staff = django_user_model.objects.create_user(username="limited-staff", is_staff=True)
    client.force_login(staff)
    assert client.get("/admin/chatbot_app/contact/").status_code == 403


@pytest.mark.django_db
def test_methods_health_and_bad_path_uuid(client):
    assert client.get("/api/chat/").status_code == 405
    assert client.post("/api/health/").status_code == 405
    assert client.get("/api/health/").json()["status"] == "ok"
    assert client.get("/api/sessions/not-a-uuid/").status_code == 400
    assert client.post("/api/sessions/").status_code == 405
