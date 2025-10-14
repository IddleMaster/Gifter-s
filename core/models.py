from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinLengthValidator, MaxValueValidator, MinValueValidator, MinValueValidator
import uuid
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from datetime import timedelta



from django.contrib.auth.models import BaseUserManager

class genero(models.TextChoices):
    MASCULINO = 'M', 'Masculino'
    FEMENINO = 'F', 'Femenino'
    OTRO = 'O', 'Otro'
    NO_DECLARADO = 'N', 'No declarado'
    

class UserManager(BaseUserManager):
    def create_user(self, correo, nombre, apellido, nombre_usuario=None, password=None, **extra_fields):
        if not correo:
            raise ValueError("El usuario debe tener un correo electrónico")
        correo = self.normalize_email(correo)

        user = self.model(
            correo=correo,
            nombre=nombre,
            apellido=apellido,
            nombre_usuario=nombre_usuario or '',  # se autogenera en User.save() si viene vacío
            **extra_fields
        )
        user.set_password(password)  # None => contraseña “no usable”, válido para registros sociales
        user.save(using=self._db)
        return user

    def create_superuser(self, correo, nombre, apellido, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("es_admin", True)

        if password is None:
            raise ValueError("El superusuario debe tener contraseña")

        return self.create_user(
            correo=correo,
            nombre=nombre,
            apellido=apellido,
            nombre_usuario='',   # lo autogenerará tu modelo en save()
            password=password,
            **extra_fields
        )

    
    
class User(AbstractBaseUser, PermissionsMixin):

    @property
    def amigos_qs(self):
        # QuerySet de usuarios que tienen follow mutuo conmigo
        return Seguidor.objects.amigos_de(self)
    # PK llamada 'id' para Django, columna en BD = id_usuario
    id = models.AutoField(primary_key=True, db_column='id_usuario')

    nombre = models.CharField(max_length=100, default='')
    apellido = models.CharField(max_length=100, default='')
    correo = models.EmailField(unique=True, default='')
    nombre_usuario = models.CharField(max_length=50, unique=True, blank=True)
    es_admin = models.BooleanField(default=False)
    genero = models.CharField(
        max_length=1, 
        choices=genero.choices,
        default=genero.NO_DECLARADO
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # <-- NUEVO

    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    token_created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre", "apellido"]

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def save(self, *args, **kwargs):
        if not self.nombre_usuario:
            base = f"{self.nombre}{self.apellido}".replace(" ", "").lower()
            candidate, i = base, 1
            while User.objects.filter(nombre_usuario=candidate).exclude(pk=self.pk).exists():
                candidate, i = f"{base}{i}", i + 1
            self.nombre_usuario = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.correo})"

    # --- Método para validación de expiración del token ---
    def is_verification_token_expired(self):
        """Devuelve True si el token de verificación ya expiró (ej: 24 horas)."""
        return timezone.now() - self.token_created_at > timedelta(hours=24)



#matiasq
class Pais(models.Model):
    id_pais = models.AutoField(primary_key=True, verbose_name='ID País')
    nombre_pais = models.CharField(max_length=100, unique=True, verbose_name='Nombre del País')

    class Meta:
        db_table = 'pais'
        verbose_name = 'País'
        verbose_name_plural = 'Países'
        ordering = ['nombre_pais']

    def __str__(self):
        return self.nombre_pais


class Region(models.Model):
    id_region = models.AutoField(primary_key=True, verbose_name='ID Región')
    nombre_region = models.CharField(max_length=100, verbose_name='Nombre de la Región')
    id_pais = models.ForeignKey(
        Pais,
        on_delete=models.CASCADE,
        db_column='id_pais',
        verbose_name='País',
        related_name='regiones'
    )

    class Meta:
        db_table = 'region'
        verbose_name = 'Región'
        verbose_name_plural = 'Regiones'
        ordering = ['nombre_region']
        constraints = [
            models.UniqueConstraint(fields=['nombre_region', 'id_pais'], name='uniq_region_por_pais')
        ]
        indexes = [
            models.Index(fields=['id_pais'], name='idx_region_pais')
        ]

    def __str__(self):
        return f"{self.nombre_region} ({self.id_pais})"


class Comuna(models.Model):
    id_comuna = models.AutoField(primary_key=True, verbose_name='ID Comuna')
    nombre_comuna = models.CharField(max_length=100, verbose_name='Nombre de la Comuna')
    id_region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        db_column='id_region',
        verbose_name='Región',
        related_name='comunas'
    )

    class Meta:
        db_table = 'comuna'
        verbose_name = 'Comuna'
        verbose_name_plural = 'Comunas'
        ordering = ['nombre_comuna']
        constraints = [
            models.UniqueConstraint(fields=['nombre_comuna', 'id_region'], name='uniq_comuna_por_region')
        ]
        indexes = [
            models.Index(fields=['id_region'], name='idx_comuna_region')
        ]

    def __str__(self):
        return f"{self.nombre_comuna} ({self.id_region})"


class Direccion(models.Model):
    id_direccion = models.AutoField(primary_key=True, verbose_name='ID Dirección')
    id_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        verbose_name='Usuario',
        related_name='direcciones'
    )
    calle = models.CharField(max_length=150, verbose_name='Calle o Avenida')
    # Puede ser "S/N" o "123A"
    numero = models.CharField(max_length=10, verbose_name='Número', help_text='Permite "S/N" o "123A"')
    id_comuna = models.ForeignKey(
        Comuna,
        on_delete=models.CASCADE,
        db_column='id_comuna',
        verbose_name='Comuna',
        related_name='direcciones'
    )

    class Meta:
        db_table = 'direccion'
        verbose_name = 'Dirección'
        verbose_name_plural = 'Direcciones'
        ordering = ['calle', 'numero']
        indexes = [
            models.Index(fields=['id_usuario'], name='idx_dir_usuario'),
            models.Index(fields=['id_comuna'], name='idx_dir_comuna')
        ]

    def __str__(self):
        return f"{self.calle} {self.numero}, {self.id_comuna}"
    
class HistorialBusqueda(models.Model):
    id_search = models.AutoField(primary_key=True, verbose_name='ID Búsqueda')
    id_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_user',
        verbose_name='Usuario',
        related_name='historial_busquedas'
    )
    term = models.CharField(
        max_length=150,
        verbose_name='Término de búsqueda'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de búsqueda'
    )

    class Meta:
        db_table = 'HistorialBusqueda'
        verbose_name = 'Historial de búsqueda'
        verbose_name_plural = 'Historial de búsquedas'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['id_user'], name='idx_histbusq_user'),
            models.Index(fields=['term'], name='idx_histbusq_term'),
        ]

    def __str__(self):
        return f"{self.id_user.nombre_usuario} buscó '{self.term}' el {self.fecha_creacion:%Y-%m-%d %H:%M}"

class ReporteStrike(models.Model):
    id_reporte = models.AutoField(primary_key=True, verbose_name='ID Reporte')

    id_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_user',
        related_name='reportes_realizados',
        verbose_name='Usuario que reporta'
    )

    id_post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        db_column='id_post',
        related_name='reportes',
        verbose_name='Publicación reportada'
    )

    motivo = models.CharField(max_length=100, verbose_name='Motivo')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')

    class Meta:
        db_table = 'Reporte_strike'
        verbose_name = 'Reporte'
        verbose_name_plural = 'Reportes'
        ordering = ['-fecha_creacion']
        constraints = [
            models.UniqueConstraint(fields=['id_user', 'id_post'], name='uq_reporte_user_post')
        ]
        indexes = [
            models.Index(fields=['id_user'], name='idx_rep_user'),
            models.Index(fields=['id_post'], name='idx_rep_post'),
        ]

    def __str__(self):
        return f"Reporte #{self.id_reporte} de {self.id_user.nombre_usuario} sobre post {self.id_post_id}"
 

class HistorialDeRegalos(models.Model):
    id_regalo_log = models.AutoField(primary_key=True, verbose_name='ID Log de Regalo')

    id_item = models.ForeignKey(
        'ItemEnWishlist',
        on_delete=models.CASCADE,
        db_column='id_item',
        related_name='historial_regalos',
        verbose_name='Item de wishlist'
    )

    id_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_user',
        related_name='historial_regalos',
        verbose_name='Usuario que regala'
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')

    class Meta:
        db_table = 'HistorialDeRegalos'
        verbose_name = 'Historial de regalo'
        verbose_name_plural = 'Historial de regalos'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['id_item'], name='idx_histregalo_item'),
            models.Index(fields=['id_user'], name='idx_histregalo_user'),
        ]

    def __str__(self):
        return f"{self.id_user.nombre_usuario} -> item {self.id_item_id} ({self.fecha_creacion:%Y-%m-%d %H:%M})"


    



    
#ELIAS

#Wishlist, Seguidor, Post
class Wishlist(models.Model):
    id_wishlist = models.AutoField(primary_key=True, verbose_name='ID Wishlist')
    usuario = models.ForeignKey(
        'User',  # Referencia a tu modelo User personalizado
        on_delete=models.CASCADE,
        verbose_name='Usuario',
        related_name='wishlists'  # Para acceder: user.wishlists.all()
    )
    nombre_wishlist = models.CharField(
        max_length=100,
        verbose_name='Nombre de la Wishlist'
    )
    es_publica = models.BooleanField(
        default=True,
        verbose_name='¿Es pública?'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de actualización'
    )
    
    class Meta:
        db_table = 'wishlist'
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'
        ordering = ['-fecha_creacion']
        unique_together = ['usuario', 'nombre_wishlist']  # Nombre único por usuario
    
    def __str__(self):
        return f"{self.nombre_wishlist} - {self.usuario.nombre_usuario}"
    

class SeguidorQuerySet(models.QuerySet):
    def amigos_de(self, user):
        # Usuarios que sigue 'user' y que a la vez lo siguen
        return (User.objects
                .filter(seguidores__seguidor=user, siguiendo__seguido=user)
                .distinct())  

class Seguidor(models.Model):
    relacion_id = models.AutoField(primary_key=True, verbose_name='ID Relación')
    seguidor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='seguidor_id',
        verbose_name='Seguidor',
        related_name='siguiendo'  # user.siguiendo.all() → usuarios que este usuario sigue
    )
    seguido = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='seguido_id', 
        verbose_name='Seguido',
        related_name='seguidores'  # user.seguidores.all() → usuarios que siguen a este usuario
    )
    fecha_seguimiento = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de seguimiento'
    )
    
    class Meta:
        db_table = 'seguidor'
        verbose_name = 'Seguidor'
        verbose_name_plural = 'Seguidores'
        ordering = ['-fecha_seguimiento']
        # Evitar relaciones duplicadas
        constraints = [
            models.UniqueConstraint(
                fields=['seguidor', 'seguido'], 
                name='uniq_seguidor_seguido'
            )
        ]
        indexes = [
            models.Index(fields=['seguidor'], name='idx_seguidor'),
            models.Index(fields=['seguido'], name='idx_seguido'),
        ]
    
    def __str__(self):
        return f"{self.seguidor.nombre_usuario} sigue a {self.seguido.nombre_usuario}"
    
    def clean(self):
        # Evitar que un usuario se siga a sí mismo
        if self.seguidor == self.seguido:
            raise ValidationError("Un usuario no puede seguirse a sí mismo")
        
      

class Post(models.Model):
    # PK
    id_post = models.AutoField(primary_key=True, verbose_name='ID Post')
    
    # FK al usuario (autor)
    id_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        verbose_name='Autor',
        related_name='posts'
    )
    
    # Contenido del post
    contenido = models.TextField(
        verbose_name='Contenido del post',
        blank=True,
        null=True
    )
    
    # Tipo de post - usando TextChoices para mejor manejo
    class TipoPost(models.TextChoices):
        TEXTO = 'texto', 'Texto'
        IMAGEN = 'imagen', 'Imagen'
        VIDEO = 'video', 'Video'
        ENLACE = 'enlace', 'Enlace'
    
    tipo_post = models.CharField(
        max_length=10,
        choices=TipoPost.choices,
        default=TipoPost.TEXTO,
        verbose_name='Tipo de post'
    )
    
    # URL de media (opcional)
    url_media = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='URL de media'
    )
    
    # Visibilidad
    es_publico = models.BooleanField(
        default=True,
        verbose_name='¿Es público?'
    )
    
    # Fechas
    fecha_publicacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de publicación'
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de actualización'
    )
    
    class Meta:
        db_table = 'post'
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = ['-fecha_publicacion']
        indexes = [
            models.Index(fields=['id_usuario'], name='idx_post_usuario'),
            models.Index(fields=['tipo_post'], name='idx_post_tipo'),
            models.Index(fields=['es_publico'], name='idx_post_publico'),
            models.Index(fields=['fecha_publicacion'], name='idx_post_fecha'),
        ]
    
    def __str__(self):
        return f"Post {self.id_post} por {self.id_usuario.nombre_usuario}"
    
    def clean(self):
        """Validaciones personalizadas"""
        # Si es tipo imagen/video/enlace, debería tener url_media
        if self.tipo_post in [self.TipoPost.IMAGEN, self.TipoPost.VIDEO, self.TipoPost.ENLACE] and not self.url_media:
            raise ValidationError(f"Los posts de tipo {self.tipo_post} deben tener una URL de media")
        
        # Si es tipo texto, el contenido no debe estar vacío
        if self.tipo_post == self.TipoPost.TEXTO and not self.contenido:
            raise ValidationError("Los posts de texto deben tener contenido")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        

class ItemEnWishlist(models.Model):
    # PK
    id_item = models.AutoField(primary_key=True, verbose_name='ID Item')
    
    # FK a Wishlist
    id_wishlist = models.ForeignKey(
        'Wishlist',
        on_delete=models.CASCADE,
        db_column='id_wishlist',
        verbose_name='Wishlist',
        related_name='items'
    )
    
    # FK a Producto
    id_producto = models.ForeignKey(
        'Producto',
        on_delete=models.CASCADE,
        db_column='id_producto',
        verbose_name='Producto',
        related_name='en_wishlists'
    )
    
    # Cantidad deseada
    cantidad = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad deseada',
        validators=[MinValueValidator(1)]
    )
    
    # Prioridad - usando TextChoices
    class Prioridad(models.TextChoices):
        ALTA = 'alta', 'Alta'
        MEDIA = 'media', 'Media'
        BAJA = 'baja', 'Baja'
    
    prioridad = models.CharField(
        max_length=10,
        choices=Prioridad.choices,
        default=Prioridad.MEDIA,
        verbose_name='Prioridad'
    )
    
    # Notas del usuario
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas del usuario'
    )
    
    # Fechas
    fecha_agregado = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de agregado'
    )
    
    fecha_comprado = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de comprado'
    )
    
    class Meta:
        db_table = 'item_en_wishlist'
        verbose_name = 'Item en Wishlist'
        verbose_name_plural = 'Items en Wishlist'
        ordering = ['-fecha_agregado']
        # Evitar duplicados del mismo producto en la misma wishlist
        constraints = [
            models.UniqueConstraint(
                fields=['id_wishlist', 'id_producto'], 
                name='uniq_producto_por_wishlist'
            )
        ]
        indexes = [
            models.Index(fields=['id_wishlist'], name='idx_item_wishlist'),
            models.Index(fields=['id_producto'], name='idx_item_producto'),
            models.Index(fields=['prioridad'], name='idx_item_prioridad'),
            models.Index(fields=['fecha_agregado'], name='idx_item_fecha_agregado'),
        ]
    
    def __str__(self):
        return f"Item {self.id_item} - {self.id_producto.nombre_producto} en {self.id_wishlist.nombre_wishlist}"
    
    @property
    def fue_comprado(self):
        """Propiedad para verificar si el item fue comprado"""
        return self.fecha_comprado is not None
    
    def marcar_como_comprado(self):
        """Método para marcar el item como comprado"""
        if not self.fecha_comprado:
            self.fecha_comprado = timezone.now()
            self.save()
    
    def desmarcar_como_comprado(self):
        """Método para desmarcar el item como comprado"""
        if self.fecha_comprado:
            self.fecha_comprado = None
            self.save()
    
    def clean(self):
        """Validaciones personalizadas"""
        # La cantidad debe ser al menos 1
        if self.cantidad < 1:
            raise ValidationError("La cantidad debe ser al menos 1")
        
        # No permitir fecha_comprado anterior a fecha_agregado
        if self.fecha_comprado and self.fecha_comprado < self.fecha_agregado:
            raise ValidationError("La fecha de comprado no puede ser anterior a la fecha de agregado")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class RegistroActividad(models.Model):
    id_actividad = models.AutoField(
        primary_key=True,
        verbose_name='ID de actividad'
    )

    id_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='actividades',
        verbose_name='Usuario que genera la actividad'
    )

    class TipoActividad(models.TextChoices):
        NUEVO_POST     = 'nuevo_post', 'Nuevo Post'
        NUEVO_COMENT   = 'nuevo_comentario', 'Nuevo Comentario'
        NUEVA_REACCION = 'nueva_reaccion', 'Nueva Reacción'
        NUEVO_SEGUIDOR = 'nuevo_seguidor', 'Nuevo Seguidor'
        NUEVO_REGALO   = 'nuevo_regalo', 'Nuevo Regalo'
        OTRO           = 'otro', 'Otro'

    tipo_actividad = models.CharField(
        max_length=30,
        choices=TipoActividad.choices,
        verbose_name='Tipo de actividad'
    )

    # Polimórfico: referencia al elemento asociado
    id_elemento = models.PositiveIntegerField(
        verbose_name='ID del elemento relacionado'
    )
    tabla_elemento = models.CharField(
        max_length=50,
        verbose_name='Tabla del elemento (post, comentario, etc.)'
    )

    contenido_resumen = models.CharField(
        max_length=255,
        verbose_name='Resumen de la actividad'
    )

    fecha_actividad = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de la actividad'
    )

    es_publica = models.BooleanField(
        default=True,
        verbose_name='¿Se muestra en el feed de seguidores?'
    )

    class Meta:
        db_table = 'registro_actividad'
        verbose_name = 'Registro de actividad'
        verbose_name_plural = 'Registros de actividad'
        ordering = ['-fecha_actividad']
        indexes = [
            models.Index(fields=['id_usuario'], name='idx_act_usuario'),
            models.Index(fields=['tipo_actividad'], name='idx_act_tipo'),
            models.Index(fields=['fecha_actividad'], name='idx_act_fecha'),
            models.Index(fields=['es_publica'], name='idx_act_publica'),
        ]

    def __str__(self):
        return f"[{self.tipo_actividad}] {self.id_usuario.nombre_usuario} ({self.fecha_actividad:%Y-%m-%d %H:%M})"



class Comentario(models.Model):
    # PK
    id_comentario = models.AutoField(primary_key=True, verbose_name='ID Comentario')
    
    # FK al Post
    id_post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        db_column='id_post',
        verbose_name='Post',
        related_name='comentarios'
    )
    
    # FK al Usuario (autor del comentario)
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        verbose_name='Autor',
        related_name='comentarios'
    )
    
    # Contenido del comentario
    contenido = models.TextField(
        verbose_name='Contenido del comentario'
    )
    
    # Fechas
    fecha_comentario = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación'
    )
    
    fecha_edicion = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de última edición'
    )
    
    class Meta:
        db_table = 'comentario'
        verbose_name = 'Comentario'
        verbose_name_plural = 'Comentarios'
        ordering = ['fecha_comentario']  # Más antiguos primero para conversación natural
        indexes = [
            models.Index(fields=['id_post'], name='idx_comentario_post'),
            models.Index(fields=['usuario'], name='idx_comentario_usuario'),
            models.Index(fields=['fecha_comentario'], name='idx_comentario_fecha'),
        ]
    
    def __str__(self):
        return f"Comentario {self.id_comentario} por {self.usuario.nombre_usuario} en post {self.id_post_id}"
    
    def clean(self):
        """Validaciones personalizadas"""
        # El contenido no puede estar vacío
        if not self.contenido.strip():
            raise ValidationError("El comentario no puede estar vacío")
        
        # El contenido no puede ser demasiado largo (opcional)
        if len(self.contenido) > 1000:
            raise ValidationError("El comentario no puede exceder los 1000 caracteres")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def fue_editado(self):
        """Propiedad para verificar si el comentario fue editado"""
        return self.fecha_edicion > self.fecha_comentario


class Like(models.Model):
    # PK
    id_like = models.AutoField(primary_key=True, verbose_name='ID Like')
    
    # FK al Usuario
    id_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        verbose_name='Usuario',
        related_name='likes'
    )
    
    # FK al Post (opcional - puede ser NULL)
    id_post = models.ForeignKey(
        'Post',
        on_delete=models.CASCADE,
        db_column='id_post',
        verbose_name='Post',
        related_name='likes',
        blank=True,
        null=True
    )
    
    # FK al Comentario (opcional - puede ser NULL)
    id_comentario = models.ForeignKey(
        'Comentario',
        on_delete=models.CASCADE,
        db_column='id_comentario',
        verbose_name='Comentario',
        related_name='likes',
        blank=True,
        null=True
    )
    
    # Tipo de like
    class TipoLike(models.TextChoices):
        POST = 'post', 'Post'
        COMENTARIO = 'comentario', 'Comentario'
    
    tipo_like = models.CharField(
        max_length=12,
        choices=TipoLike.choices,
        verbose_name='Tipo de elemento likeado'
    )
    
    # Fecha
    fecha_like = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha del like'
    )
    
    class Meta:
        db_table = 'like'
        verbose_name = 'Like'
        verbose_name_plural = 'Likes'
        ordering = ['-fecha_like']
        # Un usuario solo puede dar like una vez al mismo elemento
        constraints = [
            models.UniqueConstraint(
                fields=['id_usuario', 'id_post'], 
                name='uniq_like_usuario_post',
                condition=models.Q(id_post__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['id_usuario', 'id_comentario'], 
                name='uniq_like_usuario_comentario',
                condition=models.Q(id_comentario__isnull=False)
            )
        ]
        indexes = [
            models.Index(fields=['id_usuario'], name='idx_like_usuario'),
            models.Index(fields=['id_post'], name='idx_like_post'),
            models.Index(fields=['id_comentario'], name='idx_like_comentario'),
            models.Index(fields=['tipo_like'], name='idx_like_tipo'),
            models.Index(fields=['fecha_like'], name='idx_like_fecha'),
        ]
    
    def __str__(self):
        if self.tipo_like == self.TipoLike.POST:
            return f"Like {self.id_like} de {self.id_usuario.nombre_usuario} al post {self.id_post_id}"
        else:
            return f"Like {self.id_like} de {self.id_usuario.nombre_usuario} al comentario {self.id_comentario_id}"
    
    def clean(self):
        """Validaciones personalizadas"""
        if not self.id_post and not self.id_comentario:
            raise ValidationError("Debe especificar un post o un comentario para el like")
        
        if self.id_post and self.id_comentario:
            raise ValidationError("No puede dar like a un post y un comentario simultáneamente")
        
        if self.id_post and self.tipo_like != self.TipoLike.POST:
            raise ValidationError("El tipo de like debe ser 'post' cuando se likea un post")
        
        if self.id_comentario and self.tipo_like != self.TipoLike.COMENTARIO:
            raise ValidationError("El tipo de like debe ser 'comentario' cuando se likea un comentario")
    
    def save(self, *args, **kwargs):
        if self.id_post:
            self.tipo_like = self.TipoLike.POST
        elif self.id_comentario:
            self.tipo_like = self.TipoLike.COMENTARIO
        
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def elemento_likeado(self):
        """Propiedad para obtener el elemento likeado"""
        return self.id_post if self.tipo_like == self.TipoLike.POST else self.id_comentario
    @classmethod
    def toggle_like_post(cls, usuario, post):
        """Alternar like en un post (dar/quitar like)"""
        like, created = cls.objects.get_or_create(
            id_usuario=usuario,
            id_post=post,
            defaults={'tipo_like': cls.TipoLike.POST}
        )
        if not created:
            like.delete()
            return False  # Like removido
        return True  # Like agregado
    
    @classmethod
    def toggle_like_comentario(cls, usuario, comentario):
        """Alternar like en un comentario (dar/quitar like)"""
        like, created = cls.objects.get_or_create(
            id_usuario=usuario,
            id_comentario=comentario,
            defaults={'tipo_like': cls.TipoLike.COMENTARIO}
        )
        if not created:
            like.delete()
            return False  # Like removido
        return True  # Like agregado
    @classmethod
    def usuario_dio_like_post(cls, usuario, post):
        """Verificar si un usuario ya dio like a un post"""
        return cls.objects.filter(id_usuario=usuario, id_post=post).exists()
    
    @classmethod
    def usuario_dio_like_comentario(cls, usuario, comentario):
        """Verificar si un usuario ya dio like a un comentario"""
        return cls.objects.filter(id_usuario=usuario, id_comentario=comentario).exists()
    
    @classmethod
    def contar_likes_post(cls, post):
        """Contar total de likes de un post"""
        return cls.objects.filter(id_post=post).count()
    
    @classmethod
    def contar_likes_comentario(cls, comentario):
        """Contar total de likes de un comentario"""
        return cls.objects.filter(id_comentario=comentario).count()
    
    @classmethod
    def obtener_likes_recientes(cls, limite=10):
        """Obtener likes más recientes"""
        return cls.objects.select_related('id_usuario', 'id_post', 'id_comentario').order_by('-fecha_like')[:limite]
    
    @classmethod
    def obtener_likes_usuario(cls, usuario, tipo=None):
        """Obtener todos los likes de un usuario, opcionalmente filtrados por tipo"""
        queryset = cls.objects.filter(id_usuario=usuario)
        if tipo:
            queryset = queryset.filter(tipo_like=tipo)
        return queryset.order_by('-fecha_like')
class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)  # Identificador único
    nombre_categoria = models.CharField(max_length=100)  # Nombre de la categoría
    descripcion = models.TextField(blank=True, null=True)  # Descripción opcional

    def __str__(self):
        return self.nombre_categoria
class Marca(models.Model):
    id_marca = models.AutoField(primary_key=True)     # Identificador único
    nombre_marca = models.CharField(max_length=100)   # Nombre de la marca

    def __str__(self):
        return self.nombre_marca
class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    nombre_producto = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=255)
    imagen = models.ImageField(upload_to="productos/", blank=True, null=True)
    id_categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    id_marca = models.ForeignKey(Marca, on_delete=models.CASCADE)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Campos de control
    activo = models.BooleanField(default=True, verbose_name='¿Activo?')
    fecha_creacion = models.DateTimeField(default=timezone.now, editable=False)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'producto'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['id_categoria'], name='idx_producto_categoria'),
            models.Index(fields=['id_marca'], name='idx_producto_marca'),
            models.Index(fields=['activo'], name='idx_producto_activo'),
        ]
    
    # Campos calculados para rating
    @property
    def rating_promedio(self):
        """Calcula el rating promedio basado en reseñas"""
        from django.db.models import Avg
        promedio = self.resenas.aggregate(Avg('calificacion'))['calificacion__avg']
        return round(promedio, 1) if promedio else 0
    
    @property
    def total_resenas(self):
        """Total de reseñas del producto"""
        return self.resenas.count()
    
    @property
    def fue_comprado(self):
        """Verifica si el producto fue comprado alguna vez"""
        return self.en_wishlists.filter(fecha_comprado__isnull=False).exists()
    
    @property
    def urls_tienda_activas(self):
        """Obtiene todas las URLs de tienda activas"""
        return self.urls_tienda.filter(activo=True)
    
    @property
    def url_tienda_principal(self):
        """Obtiene la URL de tienda principal (la primera activa)"""
        url_principal = self.urls_tienda.filter(activo=True, es_principal=True).first()
        if url_principal:
            return url_principal.url
        return self.urls_tienda.filter(activo=True).first().url if self.urls_tienda_activas.exists() else None
    
    def soft_delete(self):
        """Eliminación suave del producto"""
        self.activo = False
        self.save()
    
    def restaurar(self):
        """Restaurar producto eliminado"""
        self.activo = True
        self.save()
    
    def clean(self):
        """Validaciones del modelo"""
        if self.precio and self.precio < 0:
            raise ValidationError("El precio no puede ser negativo")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.nombre_producto


class UrlTienda(models.Model):
    """Modelo para manejar múltiples URLs de tienda por producto"""
    id_url = models.AutoField(primary_key=True)
    producto = models.ForeignKey(
        Producto, 
        on_delete=models.CASCADE, 
        related_name='urls_tienda'
    )
    url = models.URLField(max_length=500, verbose_name='URL de la tienda')
    nombre_tienda = models.CharField(max_length=100, verbose_name='Nombre de la tienda')
    es_principal = models.BooleanField(default=False, verbose_name='¿URL principal?')
    activo = models.BooleanField(default=True, verbose_name='¿Activa?')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'url_tienda'
        verbose_name = 'URL de Tienda'
        verbose_name_plural = 'URLs de Tiendas'
        ordering = ['-es_principal', 'nombre_tienda']
        constraints = [
            # Solo una URL principal por producto
            models.UniqueConstraint(
                fields=['producto', 'es_principal'], 
                condition=models.Q(es_principal=True),
                name='unique_url_principal_por_producto'
            )
        ]
        indexes = [
            models.Index(fields=['producto'], name='idx_url_producto'),
            models.Index(fields=['activo'], name='idx_url_activo'),
        ]
    
    def clean(self):
        """Validaciones"""
        if self.es_principal and not self.activo:
            raise ValidationError("Una URL principal no puede estar inactiva")
    
    def save(self, *args, **kwargs):
        # Si esta URL se marca como principal, quitar principal de otras
        if self.es_principal:
            UrlTienda.objects.filter(
                producto=self.producto, 
                es_principal=True
            ).update(es_principal=False)
        
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nombre_tienda} - {self.producto.nombre_producto}"


#jav
class Evento(models.Model):
    # PK: INT AUTO_INCREMENT con el mismo nombre de columna del Excel
    evento_id = models.AutoField(primary_key=True, db_column='evento_id')

    # FK a User usando la columna física id_usuario (tu User ya mapea id -> id_usuario)
    id_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='eventos',
        verbose_name='Usuario creador'
    )

    titulo = models.CharField(max_length=120)                 # VARCHAR
    descripcion = models.CharField(max_length=255, blank=True, null=True)  # VARCHAR
    fecha_evento = models.DateField()                         # DATE
    creado_en = models.DateTimeField(auto_now_add=True)       # TIMESTAMP
    actualizado_en = models.DateTimeField(auto_now=True)      # TIMESTAMP

    class Meta:
        db_table = 'evento'
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['-fecha_evento']
        indexes = [
            models.Index(fields=['id_usuario'], name='idx_evento_usuario'),
            models.Index(fields=['fecha_evento'], name='idx_evento_fecha'),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.fecha_evento})"


class ParticipanteDeEvento(models.Model):
    # PK INT AUTO_INCREMENT
    participante_id = models.AutoField(primary_key=True, db_column='participante_id')

    # FK al evento (usa la columna física evento_id)
    evento = models.ForeignKey(
        'core.Evento',
        on_delete=models.CASCADE,
        db_column='evento_id',
        related_name='participantes',
        verbose_name='Evento'
    )

    # FK al usuario (usa la columna física id_usuario de tu User personalizado)
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='participaciones_evento',
        verbose_name='Usuario'
    )

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'pendiente'
        ACEPTADO  = 'aceptado',  'aceptado'
        RECHAZADO = 'rechazado', 'rechazado'

    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE
    )

    class Rol(models.TextChoices):
        INVITADO     = 'invitado', 'invitado'
        ORGANIZADOR  = 'organizador', 'organizador'

    rol = models.CharField(
        max_length=12,
        choices=Rol.choices,
        default=Rol.INVITADO
    )

    agregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'participante_de_evento'              # tabla en MySQL
        verbose_name = 'Participante de evento'
        verbose_name_plural = 'Participantes de evento'
        ordering = ['-agregado_en']
        # Evita duplicar al mismo usuario en el mismo evento
        constraints = [
            models.UniqueConstraint(fields=['evento', 'usuario'], name='uq_participante_evento_usuario')
        ]
        indexes = [
            models.Index(fields=['evento'], name='idx_part_evento'),
            models.Index(fields=['usuario'], name='idx_part_usuario'),
        ]

    def __str__(self):
        return f"{self.usuario} @ {self.evento} ({self.rol}, {self.estado})"  

class InvitacionEvento(models.Model):
    invitacion_id = models.AutoField(primary_key=True, db_column='invitacion_id')

    evento = models.ForeignKey(
        'core.Evento',
        on_delete=models.CASCADE,
        db_column='evento_id',
        related_name='invitaciones'
    )

    emisor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='emisor_id',
        related_name='invitaciones_enviadas'
    )

    # En tu Excel aparece VARCHAR, pero como es FK a usuario lo correcto es INT → FK
    receptor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='receptor_id',
        related_name='invitaciones_recibidas'
    )

    class Estado(models.TextChoices):
        PENDIENTE  = 'pendiente',  'pendiente'
        ACEPTADA   = 'aceptada',   'aceptada'
        RECHAZADA  = 'rechazada',  'rechazada'
        CANCELADA  = 'cancelada',  'cancelada'

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)

    enviada_en = models.DateTimeField(auto_now_add=True)       # TIMESTAMP
    respondida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'invitacion_evento'
        verbose_name = 'Invitación a evento'
        verbose_name_plural = 'Invitaciones a evento'
        ordering = ['-enviada_en']
        indexes = [
            models.Index(fields=['evento'], name='idx_inv_evento'),
            models.Index(fields=['receptor', 'estado'], name='idx_inv_receptor_estado'),
        ]
        # Si no quieres invitaciones duplicadas para el mismo evento y receptor, descomenta:
        # constraints = [
        #     models.UniqueConstraint(fields=['evento', 'receptor'], name='uq_invitacion_evento_receptor')
        # ]

    def __str__(self):
        return f"Invitación {self.invitacion_id} → {self.receptor} [{self.estado}]"

class Notificacion(models.Model):
    notificacion_id = models.AutoField(primary_key=True, db_column='notificacion_id')

    # FK al usuario (columna física: usuario_id)
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='usuario_id',
        related_name='notificaciones'
    )

    class Tipo(models.TextChoices):
        NUEVO_MENSAJE    = 'nuevo_mensaje',    'nuevo_mensaje'
        NUEVA_INVITACION = 'nueva_invitacion', 'nueva_invitacion'
        EVENTO_PROXIMO   = 'evento_proximo',   'evento_proximo'
        SEGUIMIENTO      = 'seguimiento',      'seguimiento'
        SISTEMA          = 'sistema',          'sistema'

    tipo = models.CharField(max_length=20, choices=Tipo.choices)

    titulo  = models.CharField(max_length=120, null=True, blank=True)
    mensaje = models.CharField(max_length=255, null=True, blank=True)

    # Campo flexible para IDs/datos relacionados (JSON)
    payload = models.JSONField(null=True, blank=True)

    leida = models.BooleanField(default=False)
    creada_en = models.DateTimeField(auto_now_add=True)
    leida_en  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notificaciones'
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-creada_en']
        indexes = [
            models.Index(fields=['usuario', 'leida', 'creada_en'], name='idx_notif_usuario_leida_fecha'),
        ]

    def __str__(self):
        return f"[{self.tipo}] {self.usuario} ({'leída' if self.leida else 'no leída'})"

class Tag(models.Model):
    id_etiqueta = models.AutoField(
        primary_key=True,
        verbose_name='ID Etiqueta'
    )

    nombre_etiqueta = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Nombre de la etiqueta'
    )

    color = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Color de la etiqueta (hex o nombre)'
    )

    class Meta:
        db_table = 'tags'
        verbose_name = 'Etiqueta'
        verbose_name_plural = 'Etiquetas'
        ordering = ['nombre_etiqueta']
        indexes = [
            models.Index(fields=['nombre_etiqueta'], name='idx_tag_nombre'),
        ]

    def __str__(self):
        return f"{self.nombre_etiqueta} ({self.color or 'sin color'})"

class Resena(models.Model):
    id_resena = models.AutoField(primary_key=True, verbose_name='ID Reseña')

    id_usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='resenas',
        verbose_name='Usuario'
    )

    id_producto = models.ForeignKey(
        'Producto',
        on_delete=models.CASCADE,
        db_column='id_producto',
        related_name='resenas',
        verbose_name='Producto'
    )

    calificacion = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Calificación (1–5)'
    )

    titulo = models.CharField(max_length=150, verbose_name='Título')
    comentario = models.CharField(max_length=1000, verbose_name='Comentario')

    fecha_resena = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de reseña')

    class Meta:
        db_table = 'resena'  # evita ñ en el nombre físico
        verbose_name = 'Reseña'
        verbose_name_plural = 'Reseñas'
        ordering = ['-fecha_resena']
        constraints = [
            # Un usuario solo puede reseñar una vez cada producto
            models.UniqueConstraint(fields=['id_usuario', 'id_producto'], name='uq_resena_usuario_producto'),
            # (opcional) seguridad extra: rango válido de calificación a nivel BD en motores que lo soporten
            # models.CheckConstraint(check=models.Q(calificacion__gte=1, calificacion__lte=5), name='ck_resena_calif_1_5'),
        ]
        indexes = [
            models.Index(fields=['id_producto'], name='idx_resena_producto'),
            models.Index(fields=['id_usuario'], name='idx_resena_usuario'),
            models.Index(fields=['calificacion'], name='idx_resena_calificacion'),
        ]

    def __str__(self):
        return f"{self.id_usuario.nombre_usuario} → {self.id_producto.nombre_producto} [{self.calificacion}/5]"
        # --- Conversación ---


    
    
    
#MatiasD

class Perfil(models.Model):
    id_perfil = models.AutoField(primary_key=True)
    
    # Relación uno a uno con el modelo User
    # Si un usuario es eliminado, su perfil también lo será (on_delete=models.CASCADE)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,  
        on_delete=models.CASCADE,
        related_name='perfil',     
        db_column='id_usuario'     
    )
    
    # Biografía del usuario, puede estar en blanco
    bio = models.TextField(
        verbose_name='Biografía',
        blank=True, 
        null=True
    )
    
    # Foto de perfil, se guardará en la carpeta 'media/fotos_perfil/'
    profile_picture = models.ImageField(
        verbose_name='Foto de perfil',
        upload_to='fotos_perfil/', 
        blank=True, 
        null=True
    )
    
    # Fecha de nacimiento, puede estar en blanco
    birth_date = models.DateField(
        verbose_name='Fecha de nacimiento',
        blank=True, 
        null=True
    )

    class Meta:
        db_table = 'perfil'
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'

    def __str__(self):
        # Muestra el nombre de usuario en el admin de Django para una fácil identificación
        return f"Perfil de {self.user.nombre_usuario}"

# Preferencias de Notificaciones del Usuario
class PreferenciasUsuario(models.Model):
    id_preferencia = models.AutoField(primary_key=True)
    
    # Relación uno a uno con el modelo User
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferencias', # Para acceder: usuario.preferencias
        db_column='id_usuario'
    )
    
    # Campo para notificar sobre nuevos seguidores
    email_on_new_follower = models.BooleanField(
        default=True,
        verbose_name='Email por nuevo seguidor',
        help_text='Recibir un email cuando alguien nuevo te sigue.'
    )
    
    # Campo para notificar sobre invitaciones a eventos
    email_on_event_invite = models.BooleanField(
        default=True,
        verbose_name='Email por invitación a evento',
        help_text='Recibir un email cuando te invitan a un evento.'
    )
    
    # Campo para recordar cumpleaños
    email_on_birthday_reminder = models.BooleanField(
        default=True,
        verbose_name='Email para recordar cumpleaños',
        help_text='Recibir recordatorios por email de los cumpleaños de tus amigos.'
    )
    
    # Campo para aceptar correos de marketing
    accepts_marketing_emails = models.BooleanField(
        default=False, # Importante: Por defecto es False (opt-in)
        verbose_name='Acepta correos de marketing',
        help_text='Aceptar recibir correos con promociones y noticias.'
    )

    class Meta:
        db_table = 'preferencias_usuario'
        verbose_name = 'Preferencias de Usuario'
        verbose_name_plural = 'Preferencias de Usuarios'

    def __str__(self):
        return f"Preferencias de {self.user.nombre_usuario}"

class Insignia(models.Model):
    id_insignia = models.AutoField(primary_key=True)
    
    name = models.CharField(
        max_length=100,
        unique=True, 
        verbose_name='Nombre de la Insignia'
    )
    
    description = models.TextField(
        verbose_name='Descripción',
        help_text='Explica cómo se puede obtener esta insignia.'
    )
    
    image = models.ImageField(
        upload_to='insignias/',
        verbose_name='Imagen de la Insignia'
    )

    class Meta:
        db_table = 'insignia'
        verbose_name = 'Insignia'
        verbose_name_plural = 'Insignias'
        ordering = ['name']

    def __str__(self):
        return self.name

# 2. Modelo que registra la asignación de una Insignia a un Usuario
class InsigniaOtorgada(models.Model):
    id_ins_otorgada = models.AutoField(primary_key=True)
    
    # FK -> El usuario que ganó la insignia
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='insignias_otorgadas',
        db_column='id_usuario'
    )
    
    # FK -> La insignia específica que fue ganada
    insignia = models.ForeignKey(
        Insignia,
        on_delete=models.CASCADE,
        related_name='otorgada_a',
        db_column='id_insignia'
    )
    
    # Fecha en que se otorgó la insignia
    date_awarded = models.DateTimeField(
        auto_now_add=True, # Se establece automáticamente al crear el registro
        verbose_name='Fecha de Otorgamiento'
    )

    class Meta:
        db_table = 'insignia_otorgada'
        verbose_name = 'Insignia Otorgada'
        verbose_name_plural = 'Insignias Otorgadas'
        ordering = ['-date_awarded']
        # Restricción para que un usuario no pueda ganar la misma insignia dos veces
        constraints = [
            models.UniqueConstraint(fields=['user', 'insignia'], name='unique_user_insignia_otorgada')
        ]

    def __str__(self):
        return f"'{self.insignia.name}' otorgada a {self.user.nombre_usuario}"

class BloqueoDeUsuario(models.Model):
    id_bloqueo = models.AutoField(primary_key=True)
    
    # El usuario que realiza la acción de bloquear
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bloqueos_realizados', # -> usuario.bloqueos_realizados.all()
        verbose_name='Usuario que bloquea'
    )
    
    # El usuario que es bloqueado
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bloqueado_por', # -> usuario.bloqueado_por.all()
        verbose_name='Usuario bloqueado'
    )
    
    # La fecha y hora en que se efectuó el bloqueo
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha del bloqueo'
    )

    class Meta:
        db_table = 'bloqueo_de_usuario'
        verbose_name = 'Bloqueo de Usuario'
        verbose_name_plural = 'Bloqueos de Usuarios'
        ordering = ['-timestamp']
        # Restricción para que un usuario no pueda bloquear a la misma persona más de una vez
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_user_block')
        ]

    def clean(self):
        # Validación para evitar que un usuario se bloquee a sí mismo
        if self.blocker == self.blocked:
            raise ValidationError("Un usuario no puede bloquearse a sí mismo.")

    def save(self, *args, **kwargs):
        # Llama al método clean() antes de guardar
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.blocker.nombre_usuario} bloqueó a {self.blocked.nombre_usuario}"

class SolicitudAmistad(models.Model):
    id_solicitud = models.AutoField(primary_key=True)

    emisor = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='solicitudes_enviadas',
        db_column='emisor_id'
    )
    receptor = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='solicitudes_recibidas',
        db_column='receptor_id'
    )

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'pendiente'
        ACEPTADA  = 'aceptada',  'aceptada'
        RECHAZADA = 'rechazada', 'rechazada'
        CANCELADA = 'cancelada', 'cancelada'

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    mensaje = models.CharField(max_length=255, blank=True, null=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    respondida_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'solicitud_amistad'
        ordering = ['-creada_en']
        constraints = [
            models.UniqueConstraint(fields=['emisor', 'receptor'], name='uq_solicitud_emisor_receptor'),
        ]
        indexes = [
            models.Index(fields=['receptor', 'estado'], name='idx_sol_receptor_estado'),
            models.Index(fields=['emisor', 'estado'], name='idx_sol_emisor_estado'),
        ]

    def clean(self):
        if self.emisor_id == self.receptor_id:
            raise ValidationError("No puedes enviarte una solicitud a ti mismo.")

    def aceptar(self):
        if self.estado != self.Estado.PENDIENTE:
            return
        from core.models import Seguidor, Conversacion, ParticipanteConversacion
        # follow mutuo (idempotente)
        Seguidor.objects.get_or_create(seguidor=self.emisor, seguido=self.receptor)
        Seguidor.objects.get_or_create(seguidor=self.receptor, seguido=self.emisor)
        self.estado = self.Estado.ACEPTADA
        self.respondida_en = timezone.now()
        self.save(update_fields=['estado', 'respondida_en'])

        # buscar o crear conversación directa
        conv = (Conversacion.objects
                .filter(tipo=Conversacion.Tipo.DIRECTA, participantes__usuario=self.emisor)
                .filter(participantes__usuario=self.receptor)
                .distinct()
                .first())
        if not conv:
            conv = Conversacion.objects.create(
                tipo=Conversacion.Tipo.DIRECTA,
                creador=self.emisor,
                nombre=None
            )
            ParticipanteConversacion.objects.bulk_create([
                ParticipanteConversacion(conversacion=conv, usuario=self.emisor),
                ParticipanteConversacion(conversacion=conv, usuario=self.receptor),
            ])
        return conv

    def rechazar(self):
        if self.estado == self.Estado.PENDIENTE:
            self.estado = self.Estado.RECHAZADA
            self.respondida_en = timezone.now()
            self.save(update_fields=['estado', 'respondida_en'])

    def cancelar(self):
        if self.estado == self.Estado.PENDIENTE:
            self.estado = self.Estado.CANCELADA
            self.respondida_en = timezone.now()
            self.save(update_fields=['estado', 'respondida_en'])        


        ########## CHAT ###########


class Conversacion(models.Model):
    conversacion_id = models.AutoField(primary_key=True, db_column='conversacion_id')

    class Tipo(models.TextChoices):
        DIRECTA = 'directa', 'directa'
        GRUPO   = 'grupo',   'grupo'
        EVENTO  = 'evento',  'evento'

    tipo = models.CharField(max_length=10, choices=Tipo.choices)

    nombre = models.CharField(max_length=120, null=True, blank=True)     # para grupos/eventos
    foto_url = models.CharField(max_length=255, null=True, blank=True)

    # FK al creador (columna física id_usuario)
    creador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='conversaciones_creadas'
    )

    # FK opcional a Evento para “chat de evento”
    evento = models.ForeignKey(
        'core.Evento',
        on_delete=models.CASCADE,
        db_column='evento_id',
        related_name='conversaciones',
        null=True, blank=True
    )

    # Puntero al último mensaje (optimiza el listado de conversaciones)
    ultimo_mensaje = models.ForeignKey(
        'core.Mensaje',
        on_delete=models.SET_NULL,
        db_column='ultimo_mensaje_id',
        related_name='conversaciones_ultimas',
        null=True,
        blank=True
    )

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Estado(models.TextChoices):
        ACTIVA     = 'activa',     'activa'
        ARCHIVADA  = 'archivada',  'archivada'

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVA)

    class Meta:
        db_table = 'conversacion'
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'
        ordering = ['-actualizada_en']
        indexes = [
            models.Index(fields=['tipo'], name='idx_conv_tipo'),
            models.Index(fields=['evento'], name='idx_conv_evento'),
            models.Index(fields=['creador'], name='idx_conv_creador'),
            models.Index(fields=['ultimo_mensaje'], name='idx_conv_ultimo_mensaje'),
        ]

    def __str__(self):
        return self.nombre or f"Conversación {self.conversacion_id} ({self.tipo})"

class Mensaje(models.Model):
    mensaje_id = models.AutoField(primary_key=True, db_column='mensaje_id')

    conversacion = models.ForeignKey(
        'core.Conversacion',
        on_delete=models.CASCADE,
        db_column='conversacion_id',
        related_name='mensajes'
    )

    remitente = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='mensajes_enviados'
    )

    class Tipo(models.TextChoices):
        TEXTO   = 'texto',   'texto'
        IMAGEN  = 'imagen',  'imagen'
        ARCHIVO = 'archivo', 'archivo'
        SISTEMA = 'sistema', 'sistema'

    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.TEXTO)

    contenido = models.TextField()  # cuerpo del mensaje
    metadatos = models.JSONField(null=True, blank=True)  # urls, thumbs, etc. opcional

    creado_en  = models.DateTimeField(auto_now_add=True)
    editado_en = models.DateTimeField(null=True, blank=True)
    eliminado  = models.BooleanField(default=False)

    class Meta:
        db_table = 'mensaje'
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['conversacion', 'creado_en'], name='idx_msg_conv_fecha'),
            models.Index(fields=['remitente'], name='idx_msg_remitente'),  # <-- campo, no db_column
        ]

        def __str__(self):
            return f"Msg {self.mensaje_id} en conv {self.conversacion_id} por {self.remitente_id}"
    # --- ParticipanteConversacion ---

class ParticipanteConversacion(models.Model):
    participante_id = models.AutoField(primary_key=True, db_column='participante_id')

    conversacion = models.ForeignKey(
        'core.Conversacion',
        on_delete=models.CASCADE,
        db_column='conversacion_id',
        related_name='participantes'
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='conversaciones'
    )

    class Rol(models.TextChoices):
        MIEMBRO = 'miembro', 'miembro'
        ADMIN   = 'admin', 'admin'

    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.MIEMBRO)

    unido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'participante_conversacion'
        verbose_name = 'Participante de conversación'
        verbose_name_plural = 'Participantes de conversación'
        ordering = ['-unido_en']
        constraints = [
            models.UniqueConstraint(fields=['conversacion', 'usuario'], name='uq_conv_usuario')
        ]
        indexes = [
            models.Index(fields=['conversacion'], name='idx_partconv_conv'),
            models.Index(fields=['usuario'], name='idx_partconv_usuario'),
        ]

    def __str__(self):
        return f"{self.usuario.nombre_usuario} en {self.conversacion}"
    
class EntregaMensaje(models.Model):
    entrega_id = models.AutoField(primary_key=True, db_column='entrega_id')

    mensaje = models.ForeignKey(
        'core.Mensaje',
        on_delete=models.CASCADE,
        db_column='mensaje_id',
        related_name='entregas'
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_usuario',
        related_name='entregas_mensaje'
    )

    class Estado(models.TextChoices):
        ENTREGADO = 'entregado', 'entregado'
        LEIDO     = 'leido',     'leido'

    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ENTREGADO)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'entrega_mensaje'
        verbose_name = 'Entrega de mensaje'
        verbose_name_plural = 'Entregas de mensaje'
        ordering = ['-timestamp']
        constraints = [
            models.UniqueConstraint(fields=['mensaje', 'usuario'], name='uq_entrega_msg_usuario')
        ]
        indexes = [
            models.Index(fields=['mensaje'], name='idx_entrega_mensaje'),
            models.Index(fields=['usuario', 'estado'], name='idx_entrega_usuario_estado'),
        ]

    def __str__(self):
        return f"Entrega msg {self.mensaje_id} → user {self.usuario_id} [{self.estado}]"