from rest_framework import serializers
from core.models import User, SolicitudAmistad, Conversacion, Mensaje, ParticipanteConversacion

# ---- Usuarios ----
class UsuarioLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "nombre_usuario", "nombre", "apellido", "correo")

class UsuarioLiteWithAvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nombre_usuario", "nombre", "apellido", "correo", "avatar")

    def get_avatar(self, obj):
        p = getattr(obj, 'perfil', None)
        return p.profile_picture.url if p and p.profile_picture else None


# ---- Amistades ----
class SolicitudAmistadSerializer(serializers.ModelSerializer):
    # Si quieres avatar en solicitudes, puedes usar UsuarioLiteWithAvatarSerializer aquí también.
    emisor = UsuarioLiteSerializer(read_only=True)
    receptor = UsuarioLiteSerializer(read_only=True)

    class Meta:
        model = SolicitudAmistad
        fields = ("id_solicitud", "emisor", "receptor", "estado", "mensaje", "creada_en", "respondida_en")


# ---- Conversaciones (completa) ----
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
        return UsuarioLiteWithAvatarSerializer(users, many=True).data

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


# ---- Mensajes ----
class MensajeSerializer(serializers.ModelSerializer):
    remitente = UsuarioLiteWithAvatarSerializer(read_only=True)
    class Meta:
        model = Mensaje
        fields = ("mensaje_id", "tipo", "contenido", "remitente", "creado_en", "editado_en", "eliminado")


# ---- Conversaciones (lite para la lista del drawer) ----
class ConversacionLiteSerializer(serializers.ModelSerializer):
    ultimo_mensaje = serializers.SerializerMethodField()
    participantes = serializers.SerializerMethodField()

    class Meta:
        model = Conversacion
        fields = (
            "conversacion_id", "tipo", "nombre", "foto_url", "estado", "actualizada_en",
            "ultimo_mensaje", "participantes"
        )

    def get_ultimo_mensaje(self, obj):
        m = obj.ultimo_mensaje
        if not m:
            return None
        return {
            "mensaje_id": m.mensaje_id,
            "contenido": m.contenido,
            "tipo": m.tipo,
            "creado_en": m.creado_en,
        }

    def get_participantes(self, obj):
        users = [p.usuario for p in obj.participantes.all()]
        return UsuarioLiteWithAvatarSerializer(users, many=True).data