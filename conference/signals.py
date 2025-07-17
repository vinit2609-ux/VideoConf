# conference/signals.py

from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from .models import Participant
from django.views.decorators.csrf import csrf_exempt



@csrf_exempt
@receiver(user_logged_out)
def handle_logout(sender, request, user, **kwargs):
    # Mark all participant records as inactive for this user
    Participant.objects.filter(user=user).update(is_active=False)
