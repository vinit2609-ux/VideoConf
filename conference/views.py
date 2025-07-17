import random
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Room, Participant, Message, RecordingRequest
from .forms import RoomForm, RoomCreationForm
from .forms import JoinRoomForm
from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count
from keycloak import KeycloakOpenID,KeycloakAdmin
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from .keycloak_client import create_keycloak_user
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from .models import Meeting
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import Group
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import psutil  # For server resource usage
import logging
import os
from dotenv import load_dotenv
load_dotenv()


from django.conf import settings 





# Set up audit logger
logger = logging.getLogger('audit')
logger = logging.getLogger(__name__)





def register_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')  # password1 is used in UserCreationForm

            # Create Keycloak user
            try:
                user_id = create_keycloak_user(username, password)
            except Exception as e:
                print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$", str(e))
                return render(request, 'conference/register.html', {
                    'form': form,
                    'error': 'Keycloak user creation failed.'
                })

            # Create Django user
            user = User.objects.create_user(
                username=username,
                password=password,
                
            )
            user.save()
            return redirect('login')
        else:
            return render(request, 'conference/register.html', {'form': form})
    else:
        form = UserCreationForm()
        return render(request, 'conference/register.html', {'form': form})


def login_view(request):
    # print("Login view accessed")
    if request.method == 'POST':
        # print("POST request received")
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            # print("Form is valid")
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            KEYCLOAK_SERVER_URL = os.environ.get("server_url",None)  # or your Keycloak server URL
            KEYCLOAK_REALM = os.environ.get("realm_name", None)  # or your Keycloak realm name
            KEYCLOAK_CLIENT_ID = os.environ.get("client_id", None)
            KEYCLOAK_CLIENT_SECRET = os.environ.get("client_secret_key", None)  # if confidential client
            USERNAME = "admin"
            PASSWORD = "admin"

           
            keycloak_admin = KeycloakAdmin(
                server_url=KEYCLOAK_SERVER_URL,
                realm_name=KEYCLOAK_REALM,
                client_id=KEYCLOAK_CLIENT_ID,
                client_secret_key=KEYCLOAK_CLIENT_SECRET
            
            )
          
            # Initialize Keycloak client
            keycloak_openid = KeycloakOpenID(
                    server_url=KEYCLOAK_SERVER_URL,
                    realm_name=KEYCLOAK_REALM,
                    client_id=KEYCLOAK_CLIENT_ID,
                    client_secret_key=KEYCLOAK_CLIENT_SECRET,
            )


            try:
                username=username.lower()
                
                token = keycloak_openid.token(username,password)

                # print("$$$$$$$$$$$$$$$$$$$$$$$$ TOKEN ",token)
                # Access and refresh tokens
                access_token = token['access_token']
                refresh_token = token['refresh_token']

                print("Access Token:", access_token)
                print("Refresh Token:", refresh_token)
            except Exception as e:
                traceback.print_exc()
                print("Error!",str(e))    

            if user is not None:
                login(request, user)
                request.session['login_time'] = timezone.now().timestamp()
                return redirect('room_list')
    else:
        form = AuthenticationForm()
    return render(request, 'conference/login.html', {'form': form})


@login_required
def room_list(request):
    rooms = Room.objects.all().order_by('-created_at')
    
    # Add meeting status for each room
    for room in rooms:
        room.meeting_status_display = room.meeting_status
        if room.start_datetime:
            room.time_until_start = room.start_datetime - timezone.now()
    
    return render(request, 'conference/room_list.html', {'rooms': rooms})

@login_required
def create_room(request):
    if not is_admin(request.user):
        messages.error(request, 'You do not have permission to create a room. Please contact an admin.')
        return redirect('room_list')
    if request.method == 'POST':
        form = RoomCreationForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.created_by = request.user
            room.is_in_lobby = form.cleaned_data.get('enable_lobby', True)
            room.password = form.cleaned_data.get('room_password', '')
            
            # Handle meeting type
            meeting_type = form.cleaned_data.get('meeting_type', 'instant')
            if meeting_type == 'instant':
                room.start_datetime = timezone.now()
                room.duration = 120  # Default 2 hours for instant meetings
            else:
                room.start_datetime = form.cleaned_data.get('start_datetime')
                room.duration = form.cleaned_data.get('duration', 60)
            
            room.save()
            
            # Generate a random 6-digit room code
            room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            room.room_code = room_code
            room.save()
            
            # Room creator is always a moderator
            Participant.objects.create(
                user=request.user, 
                room=room, 
                is_moderator=True,
                is_active=True
            )
            
            # Assign additional moderators
            additional_moderators = form.cleaned_data.get('assign_moderators', [])
            for user in additional_moderators:
                Participant.objects.get_or_create(
                    user=user,
                    room=room,
                    defaults={
                        'is_moderator': True,
                        'is_active': True
                    }
                )
            
            # Assign meeting managers (add to meeting_manager group)
            meeting_managers = form.cleaned_data.get('assign_meeting_managers', [])
            meeting_manager_group, created = Group.objects.get_or_create(name='meeting_manager')
            for user in meeting_managers:
                user.groups.add(meeting_manager_group)
            
            # Generate the full room join URL
            room_url = request.build_absolute_uri(f'/room/{room.id}/')
            
            return render(request, 'conference/create_room.html', {
                'form': form,
                'room_url': room_url,
                'room_code': room_code,
                'room_created': True,
                'assigned_moderators': additional_moderators,
                'assigned_meeting_managers': meeting_managers,
            })
    else:
        form = RoomCreationForm()
    return render(request, 'conference/create_room.html', {'form': form})


# class CustomLogoutView(LogoutView):
#     """Enhanced logout view with custom template and redirect"""
#     template_name = 'conference/logout.html'
#     next_page = reverse_lazy('logout')  # Redirect to login page after logout
    
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Add custom context data
#         context['logout_message'] = "You have been securely logged out."
#         context['session_time'] = self.request.session.get('session_duration', '0')
#         return context

@login_required
def room(request, room_id):
    try:
        room = Room.objects.get(id=room_id)
        
        # Check if meeting is available at current time
        if not room.is_meeting_time:
            status = room.meeting_status
            if status == "upcoming":
                time_until = room.start_datetime - timezone.now()
                hours, remainder = divmod(time_until.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                context = {
                    'room': room,
                    'status': 'upcoming',
                    'time_until': time_str,
                    'start_time': room.start_datetime,
                    'end_time': room.end_datetime,
                }
                return render(request, 'conference/meeting_not_available.html', context)
            elif status == "ended":
                context = {
                    'room': room,
                    'status': 'ended',
                    'start_time': room.start_datetime,
                    'end_time': room.end_datetime,
                }
                return render(request, 'conference/meeting_not_available.html', context)
        
        # Check if user has been authorized for this room (password verification)
        session_key = f'room_{room_id}_authorized'
        if room.password and session_key not in request.session:
            # User hasn't been authorized yet, redirect to join room
            return redirect('join_room', room_id=room.id)
        
        # Check if user is already a participant
        participant, created = Participant.objects.get_or_create(
            user=request.user,
            room=room,
            defaults={'is_active': True}
        )
        
        # Always mark user as active when they access the room
        participant.is_active = True
        
        if created:
            # New participant - check if user should be moderator (room creator)
            if room.created_by == request.user:
                participant.is_moderator = True
            
            # Check if room has lobby enabled
            if room.is_in_lobby:
                participant.is_in_lobby = True
        
        # Ensure room creator is always a moderator
        if room.created_by == request.user and not participant.is_moderator:
            participant.is_moderator = True
        
        participant.save()
        
        context = {
            'room': room,
            'participant': participant,
            'messages': Message.objects.filter(room=room).order_by('timestamp')[:50],
            'jitsi_url': settings.JITSI_SERVER_URL,  # ✅ FIXED NAME
        }
        
        # If user is moderator, add pending recording requests they can approve
        if participant and participant.is_moderator:
            print(f"User {request.user.username} is moderator, checking for pending requests...")
            pending_requests = []
            all_requests = RecordingRequest.objects.filter(room=room, is_approved=False)
            print(f"Found {all_requests.count()} total pending requests")
            for req in all_requests:
                print(f"Checking request {req.id}: {req.requester.username} -> {req.recipient_type}")
                if can_approve_recording(request.user, room, req.recipient_type):
                    pending_requests.append(req)
                    print(f"User {request.user.username} can approve request {req.id}")
                else:
                    print(f"User {request.user.username} cannot approve request {req.id}")
            print(f"Total approvable requests for {request.user.username}: {len(pending_requests)}")
            context['pending_requests'] = pending_requests
        
        return render(request, 'conference/room.html', context)
        
    except Room.DoesNotExist:
        messages.error(request, "Room not found.")
        return redirect('room_list')

@login_required
def join_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)
 
    # Check if meeting is available at current time
    if not room.is_meeting_time:
        status = room.meeting_status
        if status == "upcoming":
            time_until = room.start_datetime - timezone.now()
            hours, remainder = divmod(time_until.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            context = {
                'room': room,
                'status': 'upcoming',
                'time_until': time_str,
                'start_time': room.start_datetime,
                'end_time': room.end_datetime,
            }
            return render(request, 'conference/meeting_not_available.html', context)
        elif status == "ended":
            context = {
                'room': room,
                'status': 'ended',
                'start_time': room.start_datetime,
                'end_time': room.end_datetime,
            }
            return render(request, 'conference/meeting_not_available.html', context)
    
    # Check if user has already been authorized for this room (password verification)
    session_key = f'room_{room_id}_authorized'
    if session_key in request.session:
        # User already verified, redirect directly to room
        return redirect('room', room_id=room.id)
    
    if request.method == 'POST':
        form = JoinRoomForm(request.POST)
        if form.is_valid():
            # Verify room code matches exactly
            entered_code = form.cleaned_data['room_code'].strip().upper()
            
            if entered_code != room.room_code:
                return render(request, 'conference/join_room.html', {
                    'room': room,
                    'form': form,
                    'error': 'Invalid room code. Please try again.',
                    'room_password': room.password
                })
            
            # Check password if room has one
            if room.password:
                if 'password' not in form.cleaned_data or form.cleaned_data['password'] != room.password:
                    return render(request, 'conference/join_room.html', {
                        'room': room,
                        'form': form,
                        'error': 'Incorrect password. Please try again.',
                        'room_password': room.password
                    })
            
            # Store authorization in session to avoid asking password again
            request.session[session_key] = True
            
            # Check if user should be moderator (room creator)
            should_be_moderator = (room.created_by == request.user)
            
            # Get or create participant, preserving moderator status
            try:
                participant = Participant.objects.get(user=request.user, room=room)
                # If user is room creator, ensure they are moderator
                if should_be_moderator and not participant.is_moderator:
                    participant.is_moderator = True
                participant.is_active = True
                participant.save()
            except Participant.DoesNotExist:
                # Create new participant
                participant = Participant.objects.create(
                    user=request.user,
                    room=room,
                    is_moderator=should_be_moderator,
                    is_active=True
                )
            
            return redirect('room', room_id=room.id)
    else:
        form = JoinRoomForm(initial={'room_id': room_id})
    
    return render(request, 'conference/join_room.html', {
        'room': room,
        'form': form,
        'room_password': room.password
    })

@login_required
def room_view(request, slug):
    room = get_object_or_404(Room, slug=slug)

    # Ensure current user is in the room
    participant, created = Participant.objects.get_or_create(
        user=request.user,
        room=room,
        defaults={'is_moderator': False}
    )

    # Get all participants
    participants = Participant.objects.filter(room=room, is_active=True).select_related('user')
    
    # Group them into chunks of 4
    grouped_participants = [participants[i:i + 4] for i in range(0, len(participants), 4)]

    return render(request, 'conference/room.html', {
        'room': room,
        "jitsi_url": settings.JITSI_SERVER_URL,
    
        'participant': participant,
        'participants': participants,
        'grouped_participants': grouped_participants,
        # Add any other required context (messages, etc.)
    })



@login_required
def leave_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    Participant.objects.filter(user=request.user, room=room).update(is_active=False)
    return HttpResponse(status=204)


@login_required
def join_meeting(request, room_id):
    meeting = get_object_or_404(Meeting, id=room_id)

    # Expired?
    if meeting.is_expired():
        messages.error(request, "Meeting has expired.")
        return redirect('home')

    # Validate passkey (GET or POST)
    if request.method == 'POST':
        passkey = request.POST.get('passkey')
        if passkey == meeting.passkey:
            request.session['authorized_room'] = room_id  # store auth
            return redirect('room_detail', room_id=room_id)
        else:
            messages.error(request, "Invalid passkey.")
    
    return render(request, 'conference/enter_passkey.html', {'meeting': meeting})


@login_required
def delete_room(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    
    if room.created_by != request.user:
        return HttpResponse("Unauthorized", status=403)

    if request.method == 'POST':
        room.delete()
        messages.success(request, "Room deleted successfully.")
    
    return redirect('room_list')


# @login_required
# def leave_room(request, room_id):
#     room = get_object_or_404(Room, id=room_id)
#     print(room_id,"KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK")
#     if request.method == 'POST':
#         Participant.objects.filter(user=request.user, room=room).update(is_active=False)
#         messages.success(request, f"You have left the room: {room.name}")
#         return redirect('room_list')  # Redirect to room list after leaving
    
#     # For GET requests, show confirmation page
#     return render(request, 'conference/leave_room.html', {
#         'room': room
#     })





@login_required
def join_room_page(request):
    # Show a page with list of rooms to join
    rooms = Room.objects.filter(is_active=True)
    return render(request, 'conference/join_room_page.html', {
        'rooms': rooms
    })
def join_room_options(request):
    rooms = Room.objects.all()
    return render(request, 'conference/join_options.html', {'rooms': rooms})





@login_required
def jitsi_meeting(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    return render(request, 'conference/jitsi_meeting.html', {
        'room': room,
        'user': request.user
    })




#  jitsi recording request for the user access






@login_required
def request_recording(request, room_id):
    if request.method == "POST":
        print(f"Recording request received for room {room_id}")
        print(f"POST data: {request.POST}")
        
        room = get_object_or_404(Room, id=room_id)
        
        # Get recipient type from request
        recipient_type = request.POST.get('recipient_type', 'moderator')
        message = request.POST.get('message', '')
        
        print(f"Recipient type: {recipient_type}, Message: {message}")
        
        # Validate recipient type
        if recipient_type not in ['admin', 'moderator', 'meeting_manager']:
            print(f"Invalid recipient type: {recipient_type}")
            return JsonResponse({"error": "Invalid recipient type"}, status=400)
        
        # Check if there are approvers for this recipient type
        approvers = get_approvers_for_room(room)
        print(f"Available approvers: {approvers}")
        
        has_approvers = any(approver['type'] == recipient_type for approver in approvers)
        print(f"Has approvers for {recipient_type}: {has_approvers}")
        
        if not has_approvers:
            print(f"No {recipient_type} available to approve requests")
            return JsonResponse({"error": f"No {recipient_type} available to approve requests"}, status=400)
        
        # Check for duplicate requests
        existing_request = RecordingRequest.objects.filter(
            room=room, 
            requester=request.user, 
            recipient_type=recipient_type, 
            is_approved=False
        ).first()
        
        if existing_request:
            print(f"Duplicate request found: {existing_request}")
            return JsonResponse({"status": "already_requested"})
        
        # Create recording request
        recording_request = RecordingRequest.objects.create(
            room=room,
            requester=request.user,
            recipient_type=recipient_type,
            message=message
        )
        # Audit log
        logger.info(f"User {request.user.username} (ID: {request.user.id}) requested recording in room {room_id} for recipient type {recipient_type} (Request ID: {recording_request.id})")
        print(f"Recording request created: {recording_request}")
        # Broadcast update to all room members
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"conference_{room_id}",
                {
                    'type': 'recording_requests_updated',
                    'room_id': room_id
                }
            )
        except Exception as e:
            print(f"WebSocket broadcast failed: {e}")
        return JsonResponse({"status": "requested"})
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

@login_required
def get_recording_requests(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    print(f"[DEBUG] get_recording_requests: user={request.user.username}, room_id={room_id}")
    is_admin_user = is_admin(request.user)
    is_moderator_user = is_moderator(request.user, room)
    is_meeting_manager_user = is_meeting_manager(request.user, room)
    print(f"[DEBUG] User roles: admin={is_admin_user}, moderator={is_moderator_user}, meeting_manager={is_meeting_manager_user}")
    all_requests = RecordingRequest.objects.filter(room=room, is_approved=False)
    print(f"[DEBUG] Found {all_requests.count()} total pending requests")
    user_approvable_requests = []
    if is_moderator_user:
        print(f"[DEBUG] User {request.user.username} is moderator: returning ALL pending requests!")
        user_approvable_requests = list(all_requests)
    else:
        for req in all_requests:
            print(f"[DEBUG] Checking request {req.id}: requester={req.requester.username}, recipient_type={req.recipient_type}")
            can_approve = can_approve_recording(request.user, room, req.recipient_type)
            print(f"[DEBUG] can_approve_recording={can_approve}")
            if can_approve:
                user_approvable_requests.append(req)
    print(f"[DEBUG] Returning {len(user_approvable_requests)} approvable requests for user {request.user.username}")
    data = {
        "requests": [
            {
                "id": r.id,
                "requester": {
                    "id": r.requester.id,
                    "username": r.requester.username
                },
                "recipient_type": r.recipient_type,
                "message": r.message,
                "timestamp": r.timestamp.isoformat()
            } for r in user_approvable_requests
        ]
    }
    print(f"[DEBUG] API response: {data}")
    return JsonResponse(data)

@login_required
def approve_recording(request, room_id, request_id):
    if request.method == "POST":
        try:
            room = get_object_or_404(Room, id=room_id)
            recording_request = get_object_or_404(RecordingRequest, id=request_id, room=room, is_approved=False)
            
            print(f"Approving recording request {request_id} by user {request.user.username}")
            
            # Check if user can approve this specific request
            if not can_approve_recording(request.user, room, recording_request.recipient_type):
                print(f"User {request.user.username} not authorized to approve request {request_id}")
                return JsonResponse({"error": "Not authorized"}, status=403)
            
            # Approve the request
            recording_request.is_approved = True
            recording_request.approved_by = request.user
            recording_request.save()
            # Audit log
            logger.info(f"User {request.user.username} (ID: {request.user.id}) approved recording request {request_id} in room {room_id} for requester {recording_request.requester.username} (ID: {recording_request.requester.id})")
            
            # Try to send WebSocket notification (but don't fail if it doesn't work)
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{recording_request.requester.id}",
                    {
                        'type': 'recording_approved',
                        'user_id': recording_request.requester.id,
                        'room_id': room_id
                    }
                )
                # Broadcast update to all room members
                async_to_sync(channel_layer.group_send)(
                    f"conference_{room_id}",
                    {
                        'type': 'recording_requests_updated',
                        'room_id': room_id
                    }
                )
                print(f"WebSocket notification sent to user {recording_request.requester.id}")
            except Exception as e:
                print(f"WebSocket notification failed: {e}")
                # Don't fail the approval if WebSocket fails
            
            # Return JSON response for AJAX
            return JsonResponse({"status": "approved"})
        except Exception as e:
            print(f"Error approving recording request: {e}")
            return JsonResponse({"error": str(e)}, status=500)

@login_required
def get_available_approvers(request, room_id):
    """Get list of available approvers for recording requests"""
    print(f"Getting available approvers for room {room_id}")
    
    room = get_object_or_404(Room, id=room_id)
    approvers = get_approvers_for_room(room)
    
    print(f"Found approvers: {approvers}")
    
    data = {
        "approvers": [
            {
                "type": approver['type'],
                "display_name": approver['display_name']
            } for approver in approvers
        ]
    }
    
    print(f"Returning data: {data}")
    return JsonResponse(data)

@login_required
def can_user_approve_recording(request, room_id):
    """Check if the current user can approve recording requests in this room"""
    print(f"Checking if user {request.user.username} can approve recording in room {room_id}")
    
    room = get_object_or_404(Room, id=room_id)
    
    # Check if user is admin
    if is_admin(request.user):
        print(f"User {request.user.username} is admin - can approve")
        return JsonResponse({"can_approve": True, "reason": "admin"})
    
    # Check if user is moderator in this room
    if is_moderator(request.user, room):
        print(f"User {request.user.username} is moderator in room {room_id} - can approve")
        return JsonResponse({"can_approve": True, "reason": "moderator"})
    
    # Check if user is meeting manager
    if is_meeting_manager(request.user, room):
        print(f"User {request.user.username} is meeting manager - can approve")
        return JsonResponse({"can_approve": True, "reason": "meeting_manager"})
    
    print(f"User {request.user.username} cannot approve recording in room {room_id}")
    return JsonResponse({"can_approve": False, "reason": "no_permission"})

def is_admin(user):
    return user.is_superuser or user.is_staff

def is_meeting_manager(user, room):
    # Check if user is in the meeting_manager group or has specific meeting manager role
    return user.groups.filter(name="meeting_manager").exists()

def can_approve_recording(user, room, recipient_type):
    """Check if user can approve recording requests for the given recipient type"""
    if recipient_type == 'admin':
        return is_admin(user)
    elif recipient_type == 'moderator':
        return is_moderator(user, room)
    elif recipient_type == 'meeting_manager':
        return is_meeting_manager(user, room)
    return False

def get_approvers_for_room(room):
    """Get all users who can approve recording requests in a room"""
    print(f"Getting approvers for room: {room.name} (ID: {room.id})")
    approvers = []
    
    # Add admins
    admins = User.objects.filter(is_superuser=True) | User.objects.filter(is_staff=True)
    print(f"Found {admins.count()} admins")
    for admin in admins:
        approvers.append({
            'user': admin,
            'type': 'admin',
            'display_name': f"{admin.username} (Admin)"
        })
    
    # Add moderators (include both active and inactive)
    moderators = Participant.objects.filter(room=room, is_moderator=True)
    print(f"Found {moderators.count()} moderators for room {room.id}")
    for participant in moderators:
        status = " (Active)" if participant.is_active else " (Inactive)"
        approvers.append({
            'user': participant.user,
            'type': 'moderator',
            'display_name': f"{participant.user.username} (Moderator{status})"
        })
    
    # Add meeting managers
    meeting_managers = User.objects.filter(groups__name="meeting_manager")
    print(f"Found {meeting_managers.count()} meeting managers")
    for manager in meeting_managers:
        approvers.append({
            'user': manager,
            'type': 'meeting_manager',
            'display_name': f"{manager.username} (Meeting Manager)"
        })
    
    print(f"Total approvers found: {len(approvers)}")
    return approvers

def is_moderator(user, room):
    try:
        participant = Participant.objects.get(user=user, room=room)
        print(f"[DEBUG] is_moderator: user={user.username}, room={room.id}, is_moderator={participant.is_moderator}")
        return participant.is_moderator
    except Participant.DoesNotExist:
        print(f"[DEBUG] is_moderator: user={user.username}, room={room.id}, participant does not exist")
        return False

@login_required
def has_recording_permission(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    print(f"Checking recording permission for user {request.user.username} in room {room_id}")
    
    # Only moderators can always record
    if is_moderator(request.user, room):
        print(f"User {request.user.username} is moderator - can record")
        return JsonResponse({"can_record": True})
    
    # Otherwise, check if user has been granted permission
    approved_requests = RecordingRequest.objects.filter(room=room, requester=request.user, is_approved=True)
    has_permission = approved_requests.exists()
    print(f"User {request.user.username} has {approved_requests.count()} approved recording requests")
    print(f"User {request.user.username} can record: {has_permission}")
    
    return JsonResponse({"can_record": has_permission})

@login_required
def manage_room_participants(request, room_id):
    """Manage participants and roles in a room"""
    try:
        room = Room.objects.get(id=room_id)
        
        # Check if user is moderator or room creator
        participant = Participant.objects.get(user=request.user, room=room)
        if not participant.is_moderator and request.user != room.created_by:
            messages.error(request, "You don't have permission to manage this room.")
            return redirect('room_list')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            user_id = request.POST.get('user_id')
            
            if action == 'add_moderator':
                user = User.objects.get(id=user_id)
                participant, created = Participant.objects.get_or_create(
                    user=user, room=room, defaults={'is_moderator': True, 'is_active': True}
                )
                if not created:
                    participant.is_moderator = True
                    participant.is_active = True
                    participant.save()
                messages.success(request, f"{user.username} is now a moderator.")
                
            elif action == 'remove_moderator':
                user = User.objects.get(id=user_id)
                if user != room.created_by:  # Can't remove room creator's moderator status
                    participant = Participant.objects.get(user=user, room=room)
                    participant.is_moderator = False
                    participant.save()
                    messages.success(request, f"{user.username} is no longer a moderator.")
                else:
                    messages.error(request, "Cannot remove room creator's moderator status.")
                    
            elif action == 'add_meeting_manager':
                user = User.objects.get(id=user_id)
                meeting_manager_group, created = Group.objects.get_or_create(name='meeting_manager')
                user.groups.add(meeting_manager_group)
                messages.success(request, f"{user.username} is now a meeting manager.")
                
            elif action == 'remove_meeting_manager':
                user = User.objects.get(id=user_id)
                meeting_manager_group = Group.objects.get(name='meeting_manager')
                user.groups.remove(meeting_manager_group)
                messages.success(request, f"{user.username} is no longer a meeting manager.")
        
        # Get current participants
        participants = Participant.objects.filter(room=room).select_related('user')
        
        # Get all users for assignment
        all_users = User.objects.filter(is_superuser=False).exclude(
            id__in=participants.values_list('user_id', flat=True)
        )
        
        # Get meeting managers
        meeting_manager_group = Group.objects.filter(name='meeting_manager').first()
        meeting_managers = meeting_manager_group.user_set.all() if meeting_manager_group else []
        
        context = {
            'room': room,
            'participants': participants,
            'all_users': all_users,
            'meeting_managers': meeting_managers,
        }
        
        return render(request, 'conference/manage_participants.html', context)
        
    except (Room.DoesNotExist, Participant.DoesNotExist):
        messages.error(request, "Room not found or you don't have access.")
        return redirect('room_list')

@login_required
def create_instant_meeting(request):
    """Create an instant meeting and redirect directly to the room"""
    if request.method == 'POST':
        print('POST data:', request.POST)
        form = RoomCreationForm(request.POST)
        print('Form is valid:', form.is_valid())
        if form.is_valid():
            room = form.save(commit=False)
            room.created_by = request.user
            room.is_in_lobby = form.cleaned_data.get('enable_lobby', True)
            room.password = form.cleaned_data.get('room_password', '')
            
            # Set instant meeting parameters
            room.start_datetime = timezone.now()
            room.duration = 120  # Default 2 hours for instant meetings
            
            room.save()
            
            # Generate a random 6-digit room code
            room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            room.room_code = room_code
            room.save()
            
            # Room creator is always a moderator
            Participant.objects.create(
                user=request.user, 
                room=room, 
                is_moderator=True,
                is_active=True
            )
            
            # Assign additional moderators
            additional_moderators = form.cleaned_data.get('assign_moderators', [])
            for user in additional_moderators:
                Participant.objects.get_or_create(
                    user=user,
                    room=room,
                    defaults={
                        'is_moderator': True,
                        'is_active': True
                    }
                )
            
            # Assign meeting managers (add to meeting_manager group)
            meeting_managers = form.cleaned_data.get('assign_meeting_managers', [])
            meeting_manager_group, created = Group.objects.get_or_create(name='meeting_manager')
            for user in meeting_managers:
                user.groups.add(meeting_manager_group)
            
            # Store authorization in session for instant meetings
            session_key = f'room_{room.id}_authorized'
            request.session[session_key] = True
            
            # Redirect directly to the room
            print('Redirecting to room:', room.id)
            return redirect('room', room_id=room.id)
        else:
            print('Instant meeting form errors:', form.errors)
    else:
        # Pre-fill form for instant meeting
        form = RoomCreationForm(initial={'meeting_type': 'instant'})
    
    return render(request, 'conference/create_instant_meeting.html', {'form': form})

@login_required
def get_room_participants(request, room_id):
    """Get all participants in a room for the management modal"""
    room = get_object_or_404(Room, id=room_id)
    
    # Check if user is moderator or room creator
    participant = get_object_or_404(Participant, user=request.user, room=room)
    if not participant.is_moderator and request.user != room.created_by:
        return JsonResponse({"error": "Not authorized"}, status=403)
    
    participants = Participant.objects.filter(room=room).select_related('user')
    
    data = {
        "participants": [
            {
                "user_id": p.user.id,
                "username": p.user.username,
                "is_moderator": p.is_moderator,
                "is_active": p.is_active,
                "is_room_creator": (p.user == room.created_by)
            } for p in participants
        ]
    }
    
    return JsonResponse(data)

@login_required
def manage_participants_api(request, room_id):
    """API endpoint for managing participants via AJAX"""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    room = get_object_or_404(Room, id=room_id)
    
    # Check if user is moderator or room creator
    participant = get_object_or_404(Participant, user=request.user, room=room)
    if not participant.is_moderator and request.user != room.created_by:
        return JsonResponse({"error": "Not authorized"}, status=403)
    
    action = request.POST.get('action')
    user_id = request.POST.get('user_id')
    
    if not action or not user_id:
        return JsonResponse({"error": "Missing action or user_id"}, status=400)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
    
    if action == 'add_moderator':
        participant, created = Participant.objects.get_or_create(
            user=user, room=room, defaults={'is_moderator': True, 'is_active': True}
        )
        if not created:
            participant.is_moderator = True
            participant.is_active = True
            participant.save()
        # Audit log
        logger.info(f"User {request.user.username} (ID: {request.user.id}) made {user.username} (ID: {user.id}) a moderator in room {room_id}")
        # Broadcast update to all room members
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"conference_{room_id}",
                {
                    'type': 'participants_updated',
                    'room_id': room_id
                }
            )
        except Exception as e:
            print(f"WebSocket broadcast failed: {e}")
        return JsonResponse({"status": "success", "message": f"{user.username} is now a moderator."})
        
    elif action == 'remove_moderator':
        if user == room.created_by:
            return JsonResponse({"error": "Cannot remove room creator's moderator status"}, status=400)
        
        participant = get_object_or_404(Participant, user=user, room=room)
        participant.is_moderator = False
        participant.save()
        # Audit log
        logger.info(f"User {request.user.username} (ID: {request.user.id}) removed moderator role from {user.username} (ID: {user.id}) in room {room_id}")
        # Broadcast update to all room members
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"conference_{room_id}",
                {
                    'type': 'participants_updated',
                    'room_id': room_id
                }
            )
        except Exception as e:
            print(f"WebSocket broadcast failed: {e}")
        return JsonResponse({"status": "success", "message": f"{user.username} is no longer a moderator."})
    
    else:
        return JsonResponse({"error": "Invalid action"}, status=400)

@login_required
@csrf_exempt
def system_utilization_stats(request):
    """API endpoint for system utilization stats (active meetings, participants, server usage)"""
    # Only allow meeting managers and admins
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    is_manager = user.groups.filter(name="meeting_manager").exists()
    if not (is_admin or is_manager):
        return JsonResponse({"error": "Not authorized"}, status=403)

    # Active meetings: Room with meeting_status == 'active'
    active_rooms = Room.objects.all()
    active_meetings = [room for room in active_rooms if room.meeting_status == 'active']
    num_active_meetings = len(active_meetings)
    num_active_participants = Participant.objects.filter(room__in=[r.id for r in active_meetings], is_active=True).count()

    # Server resource usage (CPU, memory)
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    mem_percent = mem.percent

    data = {
        "active_meetings": num_active_meetings,
        "active_participants": num_active_participants,
        "cpu_percent": cpu_percent,
        "memory_percent": mem_percent,
    }
    return JsonResponse(data)

@login_required
@csrf_exempt
def meeting_durations_api(request):
    """API endpoint for meeting durations, scheduled end times, and status for all meetings"""
    user = request.user
    is_admin = user.is_superuser or user.is_staff
    is_manager = user.groups.filter(name="meeting_manager").exists()
    if not (is_admin or is_manager):
        return JsonResponse({"error": "Not authorized"}, status=403)

    rooms = Room.objects.all()
    now = timezone.now()
    meetings = []
    for room in rooms:
        start = room.start_datetime
        duration = room.duration
        end = room.end_datetime if start else None
        status = room.meeting_status
        over_time = False
        over_time_minutes = 0
        current_duration = None
        if start:
            if status == "active":
                current_duration = int((now - start).total_seconds() // 60)
                if end and now > end:
                    over_time = True
                    over_time_minutes = int((now - end).total_seconds() // 60)
            elif status == "ended":
                current_duration = int((end - start).total_seconds() // 60) if end else None
        meetings.append({
            "room_id": room.id,
            "room_name": room.name,
            "start_time": start.isoformat() if start else None,
            "scheduled_end_time": end.isoformat() if end else None,
            "status": status,
            "current_duration_minutes": current_duration,
            "over_time": over_time,
            "over_time_minutes": over_time_minutes,
        })
    return JsonResponse({"meetings": meetings})
