from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Room, Participant, Message, RecordingRequest
from django.contrib.auth.models import Group

# --- Inlines ---
class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 1

class MessageInline(admin.TabularInline):
    model = Message
    extra = 1
    readonly_fields = ('timestamp',)

# --- Room Admin ---
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'created_by', 'created_at',
        'start_time_colored', 'end_time_colored', 'upcoming_time_colored',
        'time_left_to_start', 'meeting_duration_colored', 'is_extended'
    )
    list_filter = ('created_at',)
    search_fields = ('name', 'created_by__username')
    inlines = [ParticipantInline, MessageInline]
    date_hierarchy = 'created_at'

    def start_time_colored(self, obj):
        if not obj.start_datetime:
            return "Not set"
        return format_html('<span style="color: green;"><b>{}</b></span>', obj.start_datetime.strftime('%Y-%m-%d %H:%M'))
    start_time_colored.short_description = 'Start Time'

    def end_time_colored(self, obj):
        if not obj.end_datetime:
            return "Not set"
        return format_html('<span style="color: red;"><b>{}</b></span>', obj.end_datetime.strftime('%Y-%m-%d %H:%M'))
    end_time_colored.short_description = 'End Time'

    def upcoming_time_colored(self, obj):
        now = timezone.now()
        if obj.start_datetime and now < obj.start_datetime:
            return format_html('<span style="color: orange;"><b>Upcoming</b></span>')
        return ''
    upcoming_time_colored.short_description = 'Upcoming?'

    def time_left_to_start(self, obj):
        now = timezone.now()
        if obj.start_datetime and now < obj.start_datetime:
            delta = obj.start_datetime - now
            return str(delta).split('.')[0]
        return 'Started'
    time_left_to_start.short_description = 'Time Left to Start'

    def meeting_duration(self, obj):
        if not obj.start_datetime:
            return "Not started"
        end_time = obj.end_datetime or timezone.now()
        duration = end_time - obj.start_datetime
        return duration

    def meeting_duration_colored(self, obj):
        duration = self.meeting_duration(obj)
        if duration == "Not started":
            return duration
        scheduled_seconds = (obj.duration or 60) * 60
        color = 'red' if duration.total_seconds() > scheduled_seconds else 'green'
        return format_html(
            '<span style="color: {};"><b>{}</b></span>',
            color,
            str(duration).split('.')[0]
        )
    meeting_duration_colored.short_description = 'Meeting Duration'

    def is_extended(self, obj):
        duration = self.meeting_duration(obj)
        if duration == "Not started":
            return False
        scheduled_seconds = (obj.duration or 60) * 60
        return duration.total_seconds() > scheduled_seconds
    is_extended.boolean = True
    is_extended.short_description = 'Extended?'

# --- Participant Admin with Assign Moderator Action ---
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'is_moderator', 'is_speaker', 'joined_at')
    list_filter = ('is_moderator', 'is_speaker', 'joined_at')
    search_fields = ('user__username', 'room__name')
    list_editable = ('is_moderator', 'is_speaker')
    actions = ['assign_moderator']

    def assign_moderator(self, request, queryset):
        # Only allow Maintenance group or superuser
        if not request.user.groups.filter(name='Maintenance').exists() and not request.user.is_superuser:
            self.message_user(request, "Only Maintenance team can assign moderators.", level=messages.ERROR)
            return
        updated = queryset.update(is_moderator=True)
        self.message_user(request, f"{updated} participant(s) set as moderator.", level=messages.SUCCESS)
    assign_moderator.short_description = "Assign moderator role to selected users"

# --- Message Admin ---
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'content_short', 'timestamp', 'is_question')
    list_filter = ('is_question', 'timestamp', 'room')
    search_fields = ('content', 'user__username', 'room__name')
    
    def content_short(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_short.short_description = 'Content'

# --- Recording Request Admin ---
@admin.register(RecordingRequest)
class RecordingRequestAdmin(admin.ModelAdmin):
    list_display = ('requester', 'room', 'is_approved', 'timestamp', 'approved_by')
    list_filter = ('is_approved', 'room')
    search_fields = ('requester__username', 'room__name')
    actions = ['approve_requests']

    def approve_requests(self, request, queryset):
        updated_count = 0
        channel_layer = get_channel_layer()
        for req in queryset:
            if not req.is_approved:
                req.is_approved = True
                req.approved_by = request.user
                req.save()
                updated_count += 1
                # WebSocket Notification
                if channel_layer is not None:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{req.requester.id}",
                        {
                            "type": "recording_approved",
                            "message": "✅ Admin approved your recording request."
                        }
                    )
                else:
                    self.message_user(request, "WebSocket layer not configured. No notification sent.", level=messages.WARNING)
        self.message_user(request, f"{updated_count} request(s) successfully approved.")
    approve_requests.short_description = "Approve selected recording requests"

# --- System Utilization Dashboard (Read-only) ---
class SystemUtilizationAdmin(admin.ModelAdmin):
    verbose_name_plural = "System Utilization"
    change_list_template = "admin/system_utilization.html"

    def changelist_view(self, request, extra_context=None):
        from .models import Room, Participant
        active_meetings = Room.objects.filter(start_datetime__lte=timezone.now(), end_datetime__gte=timezone.now()).count()
        total_participants = Participant.objects.count()
        extra_context = extra_context or {}
        extra_context['active_meetings'] = active_meetings
        extra_context['total_participants'] = total_participants
        return super().changelist_view(request, extra_context=extra_context)

# Register the dashboard (dummy model)
