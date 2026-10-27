from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_view, name="chat"),
    path("sessions/", views.sessions_view, name="sessions"),
    path("api/chat/", views.api_chat, name="api_chat"),
    path("api/health/", views.health_check, name="health_check"),
    path("api/sessions/", views.api_sessions, name="api_sessions"),
    path("api/sessions/<str:session_id>/", views.api_session, name="api_session"),
    path("api/sessions/<str:session_id>/export/", views.api_session_export, name="api_session_export"),
]
