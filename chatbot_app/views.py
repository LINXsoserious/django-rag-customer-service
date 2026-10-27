"""Cookie-owned HTTP workflow with bounded input and isolated conversations."""
import json
import re
import uuid

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from rag_core.config import load_config
from rag_core.errors import RAGError

from .models import ChatMessage, ChatSession, Contact, NegativeFeedback
from .rag import answer_with_rag

MAX_BODY_BYTES = 32 * 1024
EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63})(?![\w.-])")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[ -]?)?(1[3-9]\d{9})(?!\d)")
NEGATIVE_KEYWORDS = ("不满意", "投诉", "差评", "糟糕", "失望", "不靠谱", "垃圾",
                     "unsatisfied", "complaint", "terrible", "disappointed")


def _error(code, message, status):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def _method_error(allowed):
    response = _error("method_not_allowed", "This HTTP method is not allowed.", 405)
    response["Allow"] = ", ".join(allowed)
    return response


def csrf_failure(request, reason=""):
    return _error("csrf_failed", "Refresh this page and try again with a valid CSRF token.", 403)


def _owner_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _ui_context():
    config = load_config()
    return {"backend": config.backend,
            "app_version": getattr(settings, "APP_VERSION", "0.1.0"),
            "max_question_chars": config.max_question_chars}


@ensure_csrf_cookie
def chat_view(request):
    if request.method != "GET":
        return _method_error(["GET"])
    _owner_key(request)
    return render(request, "chat.html", _ui_context())


@ensure_csrf_cookie
def sessions_view(request):
    if request.method != "GET":
        return _method_error(["GET"])
    context = _ui_context()
    context["sessions"] = ChatSession.objects.filter(owner_key=_owner_key(request)).annotate(
        message_count=Count("messages")).prefetch_related("messages")
    return render(request, "sessions.html", context)


def _parse_uuid(value):
    if not isinstance(value, str):
        raise ValueError("A UUID string is required")
    return uuid.UUID(value)


def _owned_session(request, value):
    try:
        identifier = _parse_uuid(value)
    except (ValueError, AttributeError):
        return None, _error("invalid_session_id", "The session ID must be a UUID string.", 400)
    session = ChatSession.objects.filter(session_id=identifier, owner_key=_owner_key(request)).first()
    if session is None:
        return None, _error("session_not_found", "This session was not found in this browser.", 404)
    return session, None


def _read_chat_payload(request):
    if request.content_type != "application/json":
        return None, _error("invalid_json", "Send a UTF-8 JSON object with application/json.", 400)
    try:
        declared_length = int(request.META.get("CONTENT_LENGTH") or 0)
        if declared_length > MAX_BODY_BYTES:
            return None, _error("body_too_large", "The request body exceeds 32 KiB.", 413)
        body = request.body
    except RequestDataTooBig:
        return None, _error("body_too_large", "The request body exceeds 32 KiB.", 413)
    except (TypeError, ValueError):
        return None, _error("invalid_json", "Invalid request length.", 400)
    if len(body) > MAX_BODY_BYTES:
        return None, _error("body_too_large", "The request body exceeds 32 KiB.", 413)
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None, _error("invalid_json", "The request must contain valid UTF-8 JSON.", 400)
    if not isinstance(data, dict):
        return None, _error("invalid_request", "The JSON body must be an object.", 400)
    try:
        maximum = load_config().max_question_chars
    except RAGError as exc:
        return None, _error(exc.code, exc.public_message, 503)
    message = data.get("message")
    if not isinstance(message, str) or not message.strip() or len(message) > maximum:
        return None, _error("invalid_message", f"The message must contain 1 to {maximum} characters.", 400)
    try:
        message.encode("utf-8")
    except UnicodeEncodeError:
        return None, _error("invalid_message", "The message must contain valid Unicode text.", 400)
    if data.get("lang", "zh") not in ("zh", "en"):
        return None, _error("invalid_language", "The language must be zh or en.", 400)
    if not isinstance(data.get("store_contact", False), bool):
        return None, _error("invalid_store_contact", "store_contact must be a JSON boolean.", 400)
    data["message"] = message.strip()
    return data, None


def _contact_values(message):
    values = {("email", match.group(1)) for match in EMAIL_RE.finditer(message)
              if len(match.group(1)) <= 320}
    values.update(("phone", match.group(1)) for match in PHONE_RE.finditer(message))
    return sorted(values)


def api_chat(request):
    if request.method != "POST":
        return _method_error(["POST"])
    data, error = _read_chat_payload(request)
    if error is not None:
        return error
    owner_key = _owner_key(request)
    session = None
    history = []
    if "session_id" in data:
        session, error = _owned_session(request, data["session_id"])
        if error is not None:
            return error
        recent = list(session.messages.order_by("-created_at", "-pk")[:10])
        history = [{"role": item.role, "content": item.content} for item in reversed(recent)]
    try:
        result = answer_with_rag(data["message"], chat_history=history, lang=data.get("lang", "zh"))
    except Exception as exc:
        if isinstance(exc, RAGError):
            return _error(exc.code, exc.public_message, 400 if exc.code == "invalid_question" else 503)
        return _error("rag_unavailable", "The answer service is unavailable. Please try again.", 503)

    # Provider calls finish before this transaction; failed calls leave no business records.
    with transaction.atomic():
        if session is None:
            session = ChatSession.objects.create(owner_key=owner_key)
        else:
            session = ChatSession.objects.select_for_update().filter(
                pk=session.pk, owner_key=owner_key).first()
            if session is None:
                return _error("session_not_found", "This session was not found in this browser.", 404)
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content=data["message"])
        ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT,
                                   content=result["answer"], sources=result["sources"], mode=result["mode"])
        contact_values = _contact_values(data["message"]) if data.get("store_contact", False) else []
        for contact_type, contact_value in contact_values:
            Contact.objects.get_or_create(session=session, contact_type=contact_type, contact_value=contact_value)
        lower_message = data["message"].casefold()
        keywords = [word for word in NEGATIVE_KEYWORDS if word in lower_message]
        if keywords:
            NegativeFeedback.objects.create(session=session, reason=("keyword_heuristic: " + "; ".join(keywords))[:256])
        session.save(update_fields=["updated_at"])
    response = dict(result)
    response.update(session_id=str(session.session_id), contact_recorded=bool(contact_values),
                    feedback_recorded=bool(keywords))
    return JsonResponse(response)


def _serialize_session(session, include_messages=False):
    messages = list(session.messages.all())
    first_user = next((message.content for message in messages if message.role == "user"), "")
    data = {"session_id": str(session.session_id), "user": session.user,
            "created_at": session.created_at.isoformat(), "updated_at": session.updated_at.isoformat(),
            "message_count": len(messages), "preview": first_user[:80]}
    if include_messages:
        data["messages"] = [{"id": message.pk, "role": message.role, "content": message.content,
                             "sources": message.sources, "mode": message.mode,
                             "created_at": message.created_at.isoformat()} for message in messages]
    return data


def api_sessions(request):
    if request.method != "GET":
        return _method_error(["GET"])
    sessions = ChatSession.objects.filter(owner_key=_owner_key(request)).prefetch_related("messages")
    return JsonResponse({"sessions": [_serialize_session(session) for session in sessions]})


def api_session(request, session_id):
    if request.method not in ("GET", "DELETE"):
        return _method_error(["GET", "DELETE"])
    session, error = _owned_session(request, session_id)
    if error is not None:
        return error
    if request.method == "DELETE":
        identifier = str(session.session_id)
        session.delete()
        return JsonResponse({"deleted": True, "session_id": identifier})
    return JsonResponse(_serialize_session(session, include_messages=True))


def api_session_export(request, session_id):
    if request.method != "GET":
        return _method_error(["GET"])
    session, error = _owned_session(request, session_id)
    if error is not None:
        return error
    response = JsonResponse(_serialize_session(session, include_messages=True), json_dumps_params={"ensure_ascii": False})
    response["Content-Disposition"] = f'attachment; filename="chat-{session.session_id}.json"'
    response["Cache-Control"] = "no-store"
    return response


def health_check(request):
    if request.method != "GET":
        return _method_error(["GET"])
    return JsonResponse({"status": "ok", **_ui_context()})
