from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    list_display = ['id_pais', 'nombre_pais']
    search_fields = ['nombre_pais']
    list_filter = ['nombre_pais']
# Register your models here.





class UserAdmin(BaseUserAdmin):
    # Campos que se mostrarán en la lista del admin
    list_display = ("correo", "nombre", "apellido", "nombre_usuario", "es_admin", "is_staff", "is_active")
    list_filter = ("es_admin", "is_staff", "is_active")

    # Campos para editar/crear usuarios
    fieldsets = (
        (None, {"fields": ("correo", "password")}),
        ("Información personal", {"fields": ("nombre", "apellido", "nombre_usuario")}),
        ("Permisos", {"fields": ("es_admin", "is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
        ("Verificación", {"fields": ("verification_token", "token_created_at")}),
    )

    # Campos cuando se crea un usuario nuevo en el admin
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("correo", "nombre", "apellido", "nombre_usuario", "password1", "password2", "es_admin", "is_staff", "is_active"),
        }),
    )

    search_fields = ("correo", "nombre", "apellido", "nombre_usuario")
    ordering = ("correo",)


admin.site.register(User, UserAdmin)

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['id_wishlist', 'usuario', 'nombre_wishlist', 'es_publica', 'fecha_creacion']
    list_filter = ['es_publica', 'fecha_creacion']
    search_fields = ['nombre_wishlist', 'usuario__nombre_usuario', 'usuario__correo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    raw_id_fields = ['usuario']  # Para mejor performance con muchos usuarios
    

@admin.register(Seguidor)
class SeguidorAdmin(admin.ModelAdmin):
    list_display = ['relacion_id', 'seguidor', 'seguido', 'fecha_seguimiento']
    list_filter = ['fecha_seguimiento']
    search_fields = ['seguidor__nombre_usuario', 'seguido__nombre_usuario']
    readonly_fields = ['fecha_seguimiento']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['id_post', 'id_usuario', 'tipo_post', 'es_publico', 'fecha_publicacion']
    list_filter = ['tipo_post', 'es_publico', 'fecha_publicacion']
    search_fields = ['contenido', 'id_usuario__nombre_usuario']
    readonly_fields = ['fecha_publicacion', 'fecha_actualizacion']
    date_hierarchy = 'fecha_publicacion'
    
@admin.register(ItemEnWishlist)
class ItemEnWishlistAdmin(admin.ModelAdmin):
    list_display = ['id_item', 'id_wishlist', 'id_producto', 'cantidad', 'prioridad', 'fue_comprado', 'fecha_agregado']
    list_filter = ['prioridad', 'fecha_agregado', 'fecha_comprado']
    search_fields = ['id_producto__nombre_producto', 'id_wishlist__nombre_wishlist', 'notas']
    readonly_fields = ['fecha_agregado']
    date_hierarchy = 'fecha_agregado'
    
    def fue_comprado(self, obj):
        return obj.fecha_comprado is not None
    fue_comprado.boolean = True
    fue_comprado.short_description = '¿Comprado?'
    
@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ['id_comentario', 'id_post', 'usuario', 'contenido_truncado', 'fecha_comentario', 'fue_editado']
    list_filter = ['fecha_comentario', 'fecha_edicion']
    search_fields = ['contenido', 'usuario__nombre_usuario', 'id_post__id_post']
    readonly_fields = ['fecha_comentario', 'fecha_edicion']
    date_hierarchy = 'fecha_comentario'
    
    def contenido_truncado(self, obj):
        return obj.contenido[:50] + "..." if len(obj.contenido) > 50 else obj.contenido
    contenido_truncado.short_description = 'Contenido'
    
    def fue_editado(self, obj):
        return obj.fecha_edicion > obj.fecha_comentario
    fue_editado.boolean = True
    fue_editado.short_description = '¿Editado?'
    
@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ['id_like', 'id_usuario', 'tipo_like', 'elemento_likeado', 'fecha_like']
    list_filter = ['tipo_like', 'fecha_like']
    search_fields = ['id_usuario__nombre_usuario', 'id_post__id_post', 'id_comentario__id_comentario']
    readonly_fields = ['fecha_like']
    date_hierarchy = 'fecha_like'
    
    def elemento_likeado(self, obj):
        if obj.tipo_like == Like.TipoLike.POST:
            return f"Post {obj.id_post_id}"
        else:
            return f"Comentario {obj.id_comentario_id}"
    elemento_likeado.short_description = 'Elemento Likeado'