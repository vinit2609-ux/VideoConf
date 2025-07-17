from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    re_path(r'ws/room/(?P<room_id>\w+)/$', consumers.ConferenceConsumer.as_asgi()),
    re_path(r'ws/conference/(?P<room_id>\d+)/$', consumers.ConferenceConsumer.as_asgi()),
    # re_path(r'ws/chat/(?P<room_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    # re_path(r'ws/transcription/(?P<room_id>\d+)/$', consumers.TranscriptionConsumer.as_asgi()),
]