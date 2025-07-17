# conference/models.py
from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import timedelta  

class Room(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    password = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False)
    is_in_lobby = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    room_code = models.CharField(max_length=6, unique=True, blank=True, null=True)
    start_datetime = models.DateTimeField(null=True, blank=True, help_text="When the meeting starts")
    duration = models.IntegerField(default=60, help_text="Duration in minutes")
    
    def __str__(self):
        return self.name
    
    @property
    def end_datetime(self):
        """Calculate when the meeting ends"""
        if self.start_datetime:
            return self.start_datetime + timedelta(minutes=self.duration)
        return None
    
    @property
    def is_meeting_time(self):
        """Check if current time is within the meeting window"""
        now = timezone.now()
        if not self.start_datetime:
            return True  # If no start time set, always available
        
        # Allow joining 15 minutes before start time
        early_join = self.start_datetime - timedelta(minutes=15)
        return early_join <= now <= self.end_datetime
    
    @property
    def meeting_status(self):
        """Get the current status of the meeting"""
        now = timezone.now()
        if not self.start_datetime:
            return "available"
        
        if now < self.start_datetime - timedelta(minutes=15):
            return "upcoming"
        elif now > self.end_datetime:
            return "ended"
        else:
            return "active"

class Participant(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='participants')
    is_moderator = models.BooleanField(default=False)
    is_speaker = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True) 
    joined_at = models.DateTimeField(auto_now_add=True)
    is_in_lobby = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'room')

class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_question = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}"
    
    class Meta:
        ordering = ['timestamp']

class Meeting(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True)  # Added
    name = models.CharField(max_length=100, null=True, blank=True)  # Added
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    passkey = models.CharField(max_length=10, null=True, blank=True)  # Added
    transcript = models.TextField(blank=True, null = True)  # Added
    summary = models.TextField(blank=True)  # Added
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Added

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=1)
    

class RecordingRequest(models.Model):
    RECIPIENT_CHOICES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('meeting_manager', 'Meeting Manager'),
    ]
    
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    requester = models.ForeignKey(User, on_delete=models.CASCADE)
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_CHOICES, default='moderator')
    is_approved = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_recordings')
    message = models.TextField(blank=True, help_text="Optional message with the recording request")

    def __str__(self):
        return f"{self.requester.username} -> {self.recipient_type} in {self.room.name}"



