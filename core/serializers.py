from rest_framework import serializers
from core.models import User, SolicitudAmistad
from .models import Conversacion, Mensaje
from core.models import Conversacion, Mensaje, ParticipanteConversacion

class UsuarioLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "nombre_usuario", "nombre", "apellido", "correo")

class SolicitudAmistadSerializer(serializers.ModelSerializer):
    emisor = UsuarioLiteSerializer(read_only=True)
    receptor = UsuarioLiteSerializer(read_only=True)

    class Meta:
        model = SolicitudAmistad
        fields = ("id_solicitud", "emisor", "receptor", "estado", "mensaje", "creada_en", "respondida_en")






######
class ConversacionSerializer(serializers.ModelSerializer):
    participantes = serializers.SerializerMethodField()
    ultimo_mensaje = serializers.SerializerMethodField()

    class Meta:
        model = Conversacion
        fields = (
            "conversacion_id", "tipo", "nombre", "foto_url",
            "creada_en", "actualizada_en", "participantes", "ultimo_mensaje"
        )

    def get_participantes(self, obj):
        users = User.objects.filter(conversaciones__conversacion=obj)
        return UsuarioLiteSerializer(users, many=True).data

    def get_ultimo_mensaje(self, obj):
        m = obj.ultimo_mensaje
        if not m:
            return None
        return {
            "mensaje_id": m.mensaje_id,
            "remitente_id": m.remitente_id,
            "contenido": m.contenido,
            "creado_en": m.creado_en,
        }


class MensajeSerializer(serializers.ModelSerializer):
    remitente = UsuarioLiteSerializer(read_only=True)

    class Meta:
        model = Mensaje
        fields = ("mensaje_id", "tipo", "contenido", "remitente", "creado_en", "editado_en", "eliminado")


class ConversacionLiteSerializer(serializers.ModelSerializer):
    ultimo_mensaje = serializers.SerializerMethodField()
    participantes = serializers.SerializerMethodField()

    class Meta:
        model = Conversacion
        fields = ("conversacion_id", "tipo", "nombre", "foto_url", "estado", "actualizada_en",
                  "ultimo_mensaje", "participantes")

    def get_ultimo_mensaje(self, obj):
        if not obj.ultimo_mensaje:
            return None
        return {
            "mensaje_id": obj.ultimo_mensaje.mensaje_id,
            "contenido": obj.ultimo_mensaje.contenido,
            "tipo": obj.ultimo_mensaje.tipo,
            "creado_en": obj.ultimo_mensaje.creado_en,
        }

    def get_participantes(self, obj):
        # Devolvemos usuarios (lite) de los participantes
        users = [p.usuario for p in obj.participantes.all()]
        return UsuarioLiteSerializer(users, many=True).data        