from django import forms
from .models import Room
from django.contrib.auth.models import User

class RoomForm(forms.ModelForm):
   class Meta:
        model = Room
        fields = ['name', 'description', 'is_in_lobby', 'start_datetime']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter room name'
            }),
            'start_datetime': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter room description',
                'rows': 3
            }),
            'is_in_lobby': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
   start_datetime = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        input_formats=['%Y-%m-%dT%H:%M'],
        required=False,
        label="Meeting Start Time"
    )

class RoomCreationForm(RoomForm):
    """Enhanced form for room creation with role assignment"""
    
    # Meeting type selection
    meeting_type = forms.ChoiceField(
        choices=[
            ('instant', 'Instant Meeting (Start Now)'),
            ('scheduled', 'Scheduled Meeting (Set Date & Time)')
        ],
        initial='instant',
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        label="Meeting Type",
        help_text="Choose whether to start the meeting immediately or schedule it for later"
    )
    
    # Meeting manager assignment
    assign_meeting_managers = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label="Assign Meeting Managers",
        help_text="Select users who will have meeting manager privileges in this room"
    )
    
    # Additional moderators
    assign_moderators = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        label="Assign Additional Moderators",
        help_text="Select users who will have moderator privileges in this room"
    )
    
    # Room settings
    enable_lobby = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Enable Lobby",
        help_text="Users must wait for approval before joining"
    )
    
    room_password = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional room password'
        }),
        label="Room Password",
        help_text="Optional password for additional security"
    )
    
    duration = forms.IntegerField(
        min_value=15,
        max_value=480,  # 8 hours max
        initial=60,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '60'
        }),
        label="Meeting Duration (minutes)",
        help_text="How long the meeting will last (15 minutes to 8 hours)"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users to show only non-superusers for assignment
        self.fields['assign_meeting_managers'].queryset = User.objects.filter(is_superuser=False)
        self.fields['assign_moderators'].queryset = User.objects.filter(is_superuser=False)





class JoinRoomForm(forms.Form):
    room_id = forms.IntegerField(widget=forms.HiddenInput())
    room_code = forms.CharField(
        label="Room Code",
        max_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit room code',
            'style': 'letter-spacing: 2px; font-weight: bold; text-align: center;'
        })
    )
    password = forms.CharField(
        label="Password",
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter room password'
        })
    )
 

 