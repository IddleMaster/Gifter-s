# core/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.templatetags.static import static

# ¡Asegúrate de que User y Perfil estén importados!
from .models import Conversacion, Mensaje, ParticipanteConversacion, EntregaMensaje, User, Perfil

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
        return msg

    # Función para obtener los datos del usuario (incluida la foto)
    @database_sync_to_async
    def _get_user_info(self, user_id):
        try:
            user = User.objects.select_related('perfil').get(id=user_id)
            avatar_url = static('img/avatar-placeholder.png') 

            if hasattr(user, 'perfil') and user.perfil.profile_picture:
                # --- INICIO DEL CAMBIO ---
                
                # 1. Obtenemos el path relativo de la imagen (ej: /media/fotos/img.png)
                relative_path = user.perfil.profile_picture.url
                
                # 2. Construimos la URL base desde el scope del WebSocket
                #    Esto nos dará algo como: http://localhost:8000
                scheme = self.scope['scheme'].replace('ws', 'http') # Cambia wss a https, ws a http
                host = self.scope['server'][0]
                port = self.scope['server'][1]
                base_url = f"{scheme}://{host}:{port}"

                # 3. Unimos la base y la ruta relativa para tener una URL absoluta
                #    Y la asignamos a la variable que se enviará
                avatar_url = urljoin(base_url, relative_path)
                
                # --- FIN DEL CAMBIO ---

            return {
                "id": user_id,
                "nombre_usuario": user.nombre_usuario,
                "avatar_url": avatar_url
            }
        except User.DoesNotExist:
            return None

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
            if not contenido:
                return

            # Obtenemos la información del remitente
            user_info = await self._get_user_info(self.scope["user"].id)
            if not user_info:
                return

            msg = await self._crear_mensaje(self.conv_id, user_info["id"], contenido, "texto")

            # Creamos el payload con la información del perfil
            payload = {
                "mensaje_id": msg.mensaje_id,
                "contenido": msg.contenido,
                "creado_en": msg.creado_en.isoformat(),
                "remitente_id": user_info["id"],
                "remitente_nombre_usuario": user_info["nombre_usuario"],
                "remitente_foto": user_info["avatar_url"], # <-- Enviamos la foto
            }

            # Enviamos el mensaje al grupo
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "broadcast.message", "payload": payload}
            )

    # Este método recibe los mensajes del grupo y los reenvía al cliente
    async def broadcast_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))