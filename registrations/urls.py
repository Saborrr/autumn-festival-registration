from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("success/", views.registration_success, name="registration_success"),
    path("moderator/", views.moderator_dashboard, name="moderator_dashboard"),
    path(
        "moderator/export/excel/",
        views.export_registrations_xlsx,
        name="export_registrations_xlsx",
    ),
    path(
        "moderator/export/word/",
        views.export_registrations_docx,
        name="export_registrations_docx",
    ),
    path(
        "moderator/registration/<int:registration_id>/toggle/",
        views.moderator_toggle,
        name="moderator_toggle",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registrations/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
