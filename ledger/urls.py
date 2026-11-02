from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", views.sign_up, name="signup"),
    path("transactions/", views.transaction_list, name="transactions"),
    path("transactions/export/", views.export_transactions, name="export_transactions"),
    path("imports/new/", views.import_upload, name="import_upload"),
    path("imports/<int:batch_id>/review/", views.import_review, name="import_review"),
    path("imports/<int:batch_id>/confirm/", views.import_confirm, name="import_confirm"),
    path("imports/<int:batch_id>/cancel/", views.import_cancel, name="import_cancel"),
    path("imports/<int:batch_id>/", views.import_result, name="import_result"),
    path("health/", views.health, name="health"),
]
