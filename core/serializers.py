from rest_framework import serializers
from core.models import User, SolicitudAmistad, Conversacion, Mensaje, ParticipanteConversacion, Producto, Notificacion, NotificationDevice, PreferenciasUsuario





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


class MensajeSerializer(serializers.ModelSerializer):
    remitente = UsuarioLiteWithAvatarSerializer(read_only=True)
    archivo_url = serializers.SerializerMethodField()  # <-- NUEVO

    class Meta:
        model = Mensaje
        fields = (
            "mensaje_id", "tipo", "contenido", "archivo_url",  # <-- añadido archivo_url
            "remitente", "creado_en", "editado_en", "eliminado"
        )

    def get_archivo_url(self, obj):
        md = obj.metadatos or {}
        return md.get("archivo_url")

# ---- Mensajes ----
class MensajeSerializer(serializers.ModelSerializer):
    remitente = UsuarioLiteWithAvatarSerializer(read_only=True)
    archivo_url = serializers.SerializerMethodField()

    class Meta:
        model = Mensaje
        fields = ("mensaje_id","tipo","contenido","archivo_url",
                  "remitente","creado_en","editado_en","eliminado")

    def get_archivo_url(self, obj):
        md = obj.metadatos or {}
        return md.get("archivo_url")


# ---- Conversaciones (lite para la lista del drawer) ----
class ConversacionLiteSerializer(serializers.ModelSerializer):
    ultimo_mensaje = serializers.SerializerMethodField()
    participantes = serializers.SerializerMethodField()
    is_group = serializers.SerializerMethodField()   # NUEVO
    titulo = serializers.SerializerMethodField()     # NUEVO

    class Meta:
        model = Conversacion
        fields = (
            "conversacion_id", "tipo", "nombre", "foto_url", "estado",
            "actualizada_en", "ultimo_mensaje", "participantes",
            "is_group", "titulo"  # NUEVO
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

    def get_is_group(self, obj):
        # marca como grupo por tipo o por # de participantes
        try:
            tipo_val = (obj.tipo or "").lower()
        except Exception:
            tipo_val = ""
        # Usa cache prefetch si ya está, sin hits extra a DB
        count_parts = getattr(obj, "_prefetched_objects_cache", None)
        if count_parts and "participantes" in count_parts:
            n = len(count_parts["participantes"])
        else:
            n = obj.participantes.count()
        return (tipo_val == "grupo") or (n > 2)

    def get_titulo(self, obj):
        # tu modelo a veces usa nombre, otras titulo
        return getattr(obj, "titulo", None) or getattr(obj, "nombre", None) or "Grupo"
   
   
# ---- Productos ----
class ProductoSerializer(serializers.ModelSerializer):
    # Opcional: Para mostrar el nombre de la categoría en lugar del ID
    categoria_nombre = serializers.CharField(source='id_categoria.nombre_categoria', read_only=True)
    marca_nombre = serializers.CharField(source='id_marca.nombre_marca', read_only=True)

    class Meta:
        model = Producto
        fields = (
            
            'nombre_producto', 
            'descripcion', 
            'precio', 
            'id_categoria', # Mantenemos el ID por si lo necesitas
            'categoria_nombre', # Nombre legible
            'id_marca', # Mantenemos el ID
            'marca_nombre', # Nombre legible
            'imagen', # URL de la imagen si la tienes configurada
            'activo' 
        )
        read_only_fields = ('categoria_nombre', 'marca_nombre') 
        
# ---- Usuarios (Admin) ----
class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # Incluye los campos que quieres ver y editar en la app de escritorio
        fields = (
            'id', # El ID de usuario (id_usuario en tu modelo)
            'nombre', 
            'apellido', 
            'correo', 
            'nombre_usuario',
            'is_active', # Para activar/desactivar
            'is_staff',  # Para permisos de admin Django
            'es_admin'   # Tu campo personalizado
        )
        # Define campos que solo se pueden leer (como el ID)
        read_only_fields = ('id', 'correo') # No permitimos cambiar ID ni correo directamente aquí
        # IMPORTANTE: NO incluimos 'password




# ---- Notificaciones NavBar ----
class NotificacionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="notificacion_id", read_only=True)

    class Meta:
        model = Notificacion
        fields = [
            "id", "notificacion_id", "tipo", "titulo", "mensaje",
            "payload", "leida", "creada_en", "leida_en"
        ]
        read_only_fields = ["notificacion_id", "leida", "creada_en", "leida_en"]

class NotificacionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ["tipo", "titulo", "mensaje", "payload"]

class DeviceSerializer(serializers.ModelSerializer):
    """
    Para WebPush guardaremos el objeto de suscripción completo (JSON) en 'token'.
    """
    class Meta:
        model = NotificationDevice
        fields = ["id", "token", "platform", "user_agent", "active"]
        read_only_fields = ["id", "platform", "user_agent", "active"]

class PreferenciasSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferenciasUsuario
        fields = [
            "email_on_new_follower",
            "email_on_event_invite",
            "email_on_birthday_reminder",
            "accepts_marketing_emails",
            "allow_push_web",
        ]

class NotificacionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ["leida"]  # solo esto se puede modificar vía PATCH/PUT