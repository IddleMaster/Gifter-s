import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Conversacion, Mensaje, ParticipanteConversacion, EntregaMensaje

class ChatConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def _user_in_conversation(self, user_id, conv_id):
        return ParticipanteConversacion.objects.filter(conversacion_id=conv_id, usuario_id=user_id).exists()

    @database_sync_to_async
    def _crear_mensaje(self, conv_id, user_id, contenido, tipo):
        conv = Conversacion.objects.get(pk=conv_id)
        msg = Mensaje.objects.create(
            conversacion=conv,
            remitente_id=user_id,
            tipo=tipo,
            contenido=contenido
        )
        conv.ultimo_mensaje = msg
        conv.actualizada_en = timezone.now()
        conv.save(update_fields=['ultimo_mensaje', 'actualizada_en'])

        parts = ParticipanteConversacion.objects.filter(conversacion_id=conv_id).values_list('usuario_id', flat=True)
        for uid in parts:
            if uid == user_id:
                continue
            EntregaMensaje.objects.get_or_create(mensaje=msg, usuario_id=uid)
        return msg

    async def connect(self):
        self.conv_id = int(self.scope["url_route"]["kwargs"]["conversacion_id"])
        self.group_name = f"chat_{self.conv_id}"

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        ok = await self._user_in_conversation(user.id, self.conv_id)
        if not ok:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return

        if data.get("action") == "send_message":
            contenido = (data.get("contenido") or "").strip()
            tipo = data.get("tipo") or "texto"
            if not contenido:
                return
            msg = await self._crear_mensaje(self.conv_id, self.scope["user"].id, contenido, tipo)

            payload = {
                "type": "chat.message",
                "mensaje_id": msg.mensaje_id,
                "conversacion_id": self.conv_id,
                "remitente_id": self.scope["user"].id,
                "contenido": msg.contenido,
                "tipo": msg.tipo,
                "creado_en": msg.creado_en.isoformat(),
            }
            await self.channel_layer.group_send(self.group_name, {"type": "broadcast", "payload": payload})

    async def broadcast(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
