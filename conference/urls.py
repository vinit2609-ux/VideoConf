from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import join_room, room, join_room_page, join_room_options # Add join_room_page

urlpatterns = [
    # Authentication URLs
    path('register/', views.register_user, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.room_list, name='room_list'),
    path('create/', views.create_room, name='create_room'),
    path('create-instant/', views.create_instant_meeting, name='create_instant_meeting'),
    path('room/<int:room_id>/', views.room, name='room'),
    
    # Room management
    path('room/<int:room_id>/join/', join_room, name='join_room'),
    path('join-room/',join_room_options, name='join_room_options'),
    path('room/<int:room_id>/participants/', views.room_view, name='participants'),
    path('room/<int:room_id>/delete/', views.delete_room, name='delete_room'),
    path('room/<int:room_id>/leave/', views.leave_room, name='leave_room'),
    path('room/<int:room_id>/manage-participants/', views.manage_room_participants, name='manage_room_participants'),

    # Recording API endpoints
    path('api/request-recording/<int:room_id>/', views.request_recording, name='request_recording'),
    path('api/get-recording-requests/<int:room_id>/', views.get_recording_requests, name='get_recording_requests'),
    path('api/approve-recording/<int:room_id>/<int:request_id>/', views.approve_recording, name='approve_recording'),
    path('api/get-available-approvers/<int:room_id>/', views.get_available_approvers, name='get_available_approvers'),
    path('api/has-recording-permission/<int:room_id>/', views.has_recording_permission, name='has_recording_permission'),
    path('api/can-user-approve-recording/<int:room_id>/', views.can_user_approve_recording, name='can_user_approve_recording'),
    
    # Participant management API endpoints
    path('api/get-room-participants/<int:room_id>/', views.get_room_participants, name='get_room_participants'),
    path('api/manage-participants/<int:room_id>/', views.manage_participants_api, name='manage_participants_api'),
    path('api/system-utilization-stats/', views.system_utilization_stats, name='system_utilization_stats'),
    path('api/meeting-durations/', views.meeting_durations_api, name='meeting_durations_api'),
]