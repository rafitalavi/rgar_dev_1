from django.urls import path
from accounts.views import LoginView, CreateUserView, ListUserView, UpdateUserView, DeleteUserView , UserDetailView ,PasswordResetView , UserNotificationView ,OwnerChangeUserPasswordView ,UpdateUserStatusView
from medical.views import CreateClinicView, ListClinicView, UpdateClinicView, DeleteClinicView , ClinicDetailView , ChatUsersView 

from subject_matters.views import CreateSubjectView, ListSubjectView, UpdateSubjectView , DeleteSubjectView ,SubjectDetailView

from chat.views import (
    ChatUserPickerView, RoomListView, CreatePrivateRoomView, MyAiRoomView,
    EnsureClinicGroupRoomView, CreateClinicGroupView,
    MessageListView, SendMessageView, MarkRoomReadView,
    MentionCountView, ReactMessageView,  SoftDeleteChatView , BlockUnblockUserView ,
    SendDirectMessageView ,AddGroupMembersView ,ChatRoomMembersView ,BlockUnblockGroupMemberView, ClinicReactionListView
)
from permissions_app.views import ToggleUserPermissionView ,UserPermissionsView
from chat.views_user_history import *
from notifications.views import *
from assessments.views import CreateAssessmentView , AssessmentQuestionsView , AddQuestionView ,DeleteQuestionView

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("users/", ListUserView.as_view()),
    path("users/<int:user_id>/", UserDetailView.as_view()),
    path("users/create/", CreateUserView.as_view()),
    path("users/<int:user_id>/update/", UpdateUserView.as_view()),
    path("users/password/reset/", PasswordResetView.as_view()),
    path("users/<int:user_id>/delete/", DeleteUserView.as_view()),
    path("users/notifications/",UserNotificationView.as_view()),
    path("users/<int:user_id>/change-password/",  OwnerChangeUserPasswordView.as_view(), ),
    path("users/status/<int:user_id>/", UpdateUserStatusView.as_view()), 
    path("permissions/users/<int:user_id>/",UserPermissionsView.as_view(),name="toggle-user-permission"),
    path("permissions/userstgoole/",ToggleUserPermissionView.as_view(),name="toggle-user-permission"),
    
    
    path("clinics/", ListClinicView.as_view()),
    path("clinics/create/", CreateClinicView.as_view()),
    path("clinics/<int:pk>/", ClinicDetailView.as_view()),
    path("clinics/<int:clinic_id>/update/", UpdateClinicView.as_view()),
    path("clinics/<int:clinic_id>/delete/", DeleteClinicView.as_view()),
    path(
    "chat/clinic/members/",
    ChatUsersView.as_view(),
    name="clinic-members"
),

    
    
    path("subjects/create/", CreateSubjectView.as_view()),
    path("subjects/", ListSubjectView.as_view()),
    path("subjects/<int:pk>/", SubjectDetailView.as_view()),
    path("subjects/<int:pk>/update/", UpdateSubjectView.as_view()),
    path("subjects/<int:pk>/delete/", DeleteSubjectView.as_view()),
    
    
    
    
    path("users/chat/", ChatUserPickerView.as_view()),
    path("rooms/", RoomListView.as_view()),
    path("rooms/private/create/", CreatePrivateRoomView.as_view()),
    path("rooms/ai/me/", MyAiRoomView.as_view()),
    path("rooms/group/ensure/<int:clinic_id>/", EnsureClinicGroupRoomView.as_view()),
    path("rooms/group/create/", CreateClinicGroupView.as_view()),

    path("rooms/<int:room_id>/messages/", MessageListView.as_view()),
    path("rooms/<int:room_id>/send/", SendMessageView.as_view()),
    path("rooms/<int:room_id>/read/", MarkRoomReadView.as_view()),
    path("rooms/<int:room_id>/delete/", SoftDeleteChatView.as_view()),
    path("rooms/directmesseges/", SendDirectMessageView.as_view()),   
    path("rooms/<int:room_id>/members/add/" , AddGroupMembersView.as_view()),
    path("rooms/<int:room_id>/members/", ChatRoomMembersView.as_view()),
    path("rooms/<int:room_id>/member/block/" , BlockUnblockGroupMemberView.as_view()),
    path("messages/react/", ClinicReactionListView.as_view()),

    path("mentions/count/", MentionCountView.as_view()),
   
    path("block/", BlockUnblockUserView.as_view()),
    
    path("users/<int:user_id>/rooms/", UserRoomHistoryView.as_view()),
    path("users/<int:user_id>/rooms/<int:room_id>/messages/",UserMessageHistoryView.as_view()),
    
    path("notifications/", NotificationListView.as_view()),
    path("notifications/<int:notif_id>/seen/", NotificationMarkSeenView.as_view()),
    
    
    
    path("assesments/create", CreateAssessmentView.as_view()),
    path("assessments/<int:assessment_id>/questions", AssessmentQuestionsView.as_view()),
    path("assessments/<int:assessment_id>/questions-add", AddQuestionView.as_view()),
    path("assessments/questions-del/<int:pk>/", DeleteQuestionView.as_view()),
    
    
    
]


