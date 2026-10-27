from django.contrib import admin

from .models import ChatMessage, ChatSession, Contact, NegativeFeedback


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "created_at", "updated_at")
    readonly_fields = ("session_id", "owner_key", "created_at", "updated_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "mode", "created_at")
    list_filter = ("role", "mode")
    readonly_fields = ("created_at",)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "contact_type", "created_at")
    readonly_fields = ("created_at",)


@admin.register(NegativeFeedback)
class NegativeFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "reason", "created_at")
    readonly_fields = ("created_at",)
