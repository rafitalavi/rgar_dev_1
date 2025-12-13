from django.urls import path
from accounts.views import LoginView, CreateUserView, ListUserView, UpdateUserView, DeleteUserView
from medical.views import CreateClinicView, ListClinicView, UpdateClinicView, DeleteClinicView , ClinicDetailView

from subject_matters.views import CreateSubjectView, ListSubjectView, UpdateSubjectView , DeleteSubjectView ,SubjectDetailView





urlpatterns = [
    path("login/", LoginView.as_view()),
    path("users/", ListUserView.as_view()),
    path("users/create/", CreateUserView.as_view()),
    path("users/<int:user_id>/update/", UpdateUserView.as_view()),
    path("users/<int:user_id>/delete/", DeleteUserView.as_view()),
    path("clinics/", ListClinicView.as_view()),
    path("clinics/create/", CreateClinicView.as_view()),
    path("clinics/<int:pk>/", ClinicDetailView.as_view()),
    path("clinics/<int:clinic_id>/update/", UpdateClinicView.as_view()),
    path("clinics/<int:clinic_id>/delete/", DeleteClinicView.as_view()),
    path("subjects/create/", CreateSubjectView.as_view()),
    path("subjects/", ListSubjectView.as_view()),
    path("subjects/<int:pk>/", SubjectDetailView.as_view()),
    path("subjects/<int:pk>/update/", UpdateSubjectView.as_view()),
    path("subjects/<int:pk>/delete/", DeleteSubjectView.as_view()),
]


