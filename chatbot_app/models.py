"""Customer-service data models with browser-owned conversations."""
import uuid

from django.db import models


class ChatSession(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner_key = models.CharField(max_length=64, db_index=True, editable=False)
    user = models.CharField(max_length=100, default="anonymous")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]

    def __str__(self):
        return f"Chat session {self.session_id}"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    mode = models.CharField(max_length=32, default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.role} message {self.pk}"


class Contact(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="contacts")
    contact_type = models.CharField(max_length=16, choices=[("email", "Email"), ("phone", "Phone")])
    contact_value = models.CharField(max_length=320)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "contact_type", "contact_value"],
                                                name="unique_session_contact")]

    def __str__(self):
        return f"{self.contact_type} contact {self.pk} (redacted)"


class NegativeFeedback(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="feedback")
    reason = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Keyword feedback {self.pk}"
