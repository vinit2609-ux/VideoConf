import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from .models import Room, Participant, Message
import random, string
from django.utils import timezone

import subprocess
import tempfile
import os

class ConferenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'conference_{self.room_id}'
        self.user = self.scope['user']

        room = await sync_to_async(Room.objects.get)(id=self.room_id)
        
        # Check if user should be moderator (room creator) - use sync_to_async for the comparison
        room_creator = await sync_to_async(lambda: room.created_by)()
        should_be_moderator = (room_creator == self.user)
        
        participant, created = await sync_to_async(Participant.objects.get_or_create)(
            user=self.user,
            room=room,
            defaults={'is_moderator': should_be_moderator}
        )
        
        # If participant already exists but should be moderator, update it
        if not created and should_be_moderator and not participant.is_moderator:
            participant.is_moderator = True
            await sync_to_async(participant.save)()

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
        await self.accept()

        participants = await sync_to_async(list)(
            Participant.objects.filter(room=room).select_related('user')
        )
        await self.send(text_data=json.dumps({
            'type': 'initial_participants',
            'participants': [
                {
                    'user_id': p.user.id,
                    'username': p.user.username,
                    'is_moderator': p.is_moderator,
                    'is_speaker': p.is_speaker,
                    'is_in_lobby': p.is_in_lobby
                } for p in participants
            ]
        }))

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'user_id': self.user.id,
                'username': self.user.username,
            }
        )

    async def disconnect(self, close_code):
        await sync_to_async(Participant.objects.filter(
            user=self.user,
            room_id=self.room_id
        ).update)(is_active=False)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_leave',
                'user_id': self.user.id,
                'username': self.user.username
            }
        )
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        # Remove user from their personal group
        await self.channel_layer.group_discard(
            f"user_{self.user.id}",
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'chat_message':
            await self.handle_chat_message(data)
        elif message_type == 'video_status':
            await self.handle_video_status(data)
        elif message_type == 'audio_status':
            await self.handle_audio_status(data)
        elif message_type == 'speaker_change':
            await self.handle_speaker_change(data)
        elif message_type == 'zoom_request':
            await self.handle_zoom_request(data)
        elif message_type == 'webrtc_offer':
            await self.handle_webrtc_offer(data)
        elif message_type == 'webrtc_answer':
            await self.handle_webrtc_answer(data)
        elif message_type == 'webrtc_ice_candidate':
            await self.handle_webrtc_ice_candidate(data)
        elif message_type == 'approve_user':
            await self.approve_user(data['user_id'])
        elif message_type == 'drawing':
            await self.handle_drawing(data)
        elif message_type == 'transcript_data':
            await self.handle_transcript_data(data)
        elif message_type == 'recording_approved':
            await self.handle_recording_approved(data)
        elif message_type == 'participants_updated':
            await self.participants_updated(data)
        elif message_type == 'recording_requests_updated':
            await self.recording_requests_updated(data)

    async def user_join(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'user_id': event['user_id'],
            'username': event['username'],
        }))

    async def user_leave(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'user_id': event['user_id'],
            'username': event['username'],
        }))

    async def handle_chat_message(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'username': data['username'],
                'message': data['message'],
                'is_question': data.get('is_question', False)
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'username': event['username'],
            'message': event['message'],
            'is_question': event['is_question']
        }))

    async def handle_audio_status(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'audio_status',
                'user_id': self.user.id,
                'audio_on': data['audio_on']
            }
        )

    async def audio_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'audio_status',
            'user_id': event['user_id'],
            'audio_on': event['audio_on']
        }))

    async def handle_video_status(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'video_status',
                'user_id': self.user.id,
                'video_on': data['video_on']
            }
        )

    async def video_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'video_status',
            'user_id': event['user_id'],
            'video_on': event['video_on']
        }))

    async def handle_speaker_change(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'speaker_change',
                'speaker_id': data['speaker_id']
            }
        )

    async def speaker_change(self, event):
        await self.send(text_data=json.dumps({
            'type': 'speaker_change',
            'speaker_id': event['speaker_id']
        }))

    async def handle_zoom_request(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'zoom_request',
                'user_id': data['user_id'],
                'username': data['username'],
                'zoom': data['zoom']
            }
        )

    async def zoom_request(self, event):
        await self.send(text_data=json.dumps({
            'type': 'zoom_request',
            'user_id': event['user_id'],
            'username': event['username'],
            'zoom': event['zoom']
        }))

    async def handle_webrtc_offer(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_offer',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'target_user_id': data['target_user_id'],
                'offer': data['offer']
            }
        )

    async def handle_webrtc_answer(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_answer',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'target_user_id': data['target_user_id'],
                'answer': data['answer']
            }
        )

    async def handle_webrtc_ice_candidate(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'webrtc_ice_candidate',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'target_user_id': data['target_user_id'],
                'candidate': data['candidate']
            }
        )

    async def webrtc_offer(self, event):
        await self.send(text_data=json.dumps({
            'type': 'webrtc_offer',
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'target_user_id': event['target_user_id'],
            'offer': event['offer']
        }))

    async def webrtc_answer(self, event):
        await self.send(text_data=json.dumps({
            'type': 'webrtc_answer',
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'target_user_id': event['target_user_id'],
            'answer': event['answer']
        }))

    async def webrtc_ice_candidate(self, event):
        await self.send(text_data=json.dumps({
            'type': 'webrtc_ice_candidate',
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'target_user_id': event['target_user_id'],
            'candidate': event['candidate']
        }))

    async def handle_drawing(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "forward_drawing",
                "payload": data
            }
        )

    async def forward_drawing(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    async def handle_transcript_data(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'transcript_data',
                'user_id': self.user.id,
                'username': self.user.username,
                'text': data['text'],
                'is_final': data['is_final']
            }
        )

    async def transcript_data(self, event):
        await self.send(text_data=json.dumps({
            'type': 'transcript_data',
            'user_id': event['user_id'],
            'username': event['username'],
            'text': event['text'],
            'is_final': event['is_final']
        }))

    async def handle_recording_approved(self, data):
        await self.channel_layer.group_send(
            f"user_{data['user_id']}",
            {
                'type': 'recording_approved',
                'user_id': data['user_id'],
                'room_id': self.room_id
            }
        )

    async def recording_approved(self, event):
        await self.send(text_data=json.dumps({
            'type': 'recording_approved',
            'user_id': event['user_id'],
            'room_id': event['room_id']
        }))

    async def approve_user(self, user_id):
        participant = await sync_to_async(Participant.objects.get)(user_id=user_id, room_id=self.room_id)
        participant.is_in_lobby = False
        await sync_to_async(participant.save)()

        await self.channel_layer.group_send(
            f"user_{user_id}",
            {
                "type": "approved",
                "room_id": self.room_id
            }
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_approved_broadcast',
                'user_id': user_id
            }
        )

    async def approved(self, event):
        await self.send(text_data=json.dumps({
            'type': 'approved',
            'room_id': event['room_id']
        }))

    async def user_approved_broadcast(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_approved_broadcast',
            'user_id': event['user_id']
        }))

    async def participants_updated(self, event):
        await self.send(text_data=json.dumps({
            'type': 'participants_updated',
            'room_id': event['room_id']
        }))

    async def recording_requests_updated(self, event):
        await self.send(text_data=json.dumps({
            'type': 'recording_requests_updated',
            'room_id': event['room_id']
        }))

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'conference_{self.room_id}'
        self.user = self.scope['user']

        room = await sync_to_async(Room.objects.get)(id=self.room_id)

        # Check if user should be moderator (room creator)
        should_be_moderator = (room.created_by == self.user)

        participant, created = await sync_to_async(Participant.objects.get_or_create)(
            user=self.user,
            room=room,
            defaults={'is_moderator': should_be_moderator, 'is_in_lobby': True}
        )
        
        # If participant already exists but should be moderator, update it
        if not created and should_be_moderator and not participant.is_moderator:
            participant.is_moderator = True
            await sync_to_async(participant.save)()

        if participant.is_moderator:
            participant.is_in_lobby = False
            await sync_to_async(participant.save)()

        if participant.is_in_lobby:
            await self.accept()
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            # Also add user to their personal group for notifications
            await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
            await self.send(text_data=json.dumps({
                'type': 'waiting_room',
                'message': 'Waiting for moderator approval...'
            }))
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        # Also add user to their personal group for notifications
        await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)
        await self.accept()

def is_moderator(user, room):
    try:
        return Participant.objects.get(user=user, room=room).is_moderator
    except Participant.DoesNotExist:
        return False



