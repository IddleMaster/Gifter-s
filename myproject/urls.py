from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static
from django.conf import settings

from core import views
from core.views import (
    EnviarSolicitudAmistad, SolicitudesRecibidasList, SolicitudesEnviadasList,
    AceptarSolicitud, RechazarSolicitud, CancelarSolicitud,
    AmigosList, EliminarAmigo,
    ConversacionesList, MensajesListCreate,toggle_like_post_view, get_comments_view,
)

#from resenas import views as resenas_views




urlpatterns = [
    # Admin / auth
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),

    # Páginas base
    path('', views.home, name='home'),
    path('login/', RedirectView.as_view(pattern_name='account_login', permanent=False), name='login'),
    path('register/', views.register_view, name='register'),
    path('service-details.html', TemplateView.as_view(template_name='service-details.html'), name='detallesServicio'),
    path('starter-page.html', TemplateView.as_view(template_name='starter-page.html'), name='StartPage'),
    path('ayuda.html', TemplateView.as_view(template_name='ayuda.html'), name='ayuda'),

    # Perfil
    path('perfil/', views.profile_view, name='perfil'),
    path('perfil/editar/', views.profile_edit, name='perfil_editar'),
    path('perfil/eventos/crear/', views.evento_crear, name='evento_crear'),
    path('perfil/eventos/<int:evento_id>/editar/', views.evento_editar, name='evento_editar'),
    path("perfil/eventos/<int:evento_id>/eliminar/", views.evento_eliminar, name="evento_eliminar"),

    # Verificación por email
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email_view, name='verify_email'),

    # Productos (una sola ruta para listado, sin duplicados)
    path('productos/', views.productos_list, name='productos_list'),
    path('producto/<int:producto_id>/', views.producto_detalle, name='producto_detalle'),
    path('productos/buscar/', views.buscar_productos, name='buscar_productos'),
    path('buscar-sugerencias/', views.buscar_sugerencias, name='buscar_sugerencias'),

    # Gestión de productos (admin)
    path('admin/productos/', views.administrar_productos, name='administrar_productos'),
    path('admin/producto/crear/', views.producto_crear, name='producto_crear'),
    path('admin/producto/editar/<int:producto_id>/', views.producto_editar, name='producto_editar'),
    path('admin/producto/eliminar/<int:producto_id>/', views.producto_eliminar, name='producto_eliminar'),
    path('admin/producto/restaurar/<int:producto_id>/', views.producto_restaurar, name='producto_restaurar'),
    path('admin/url-tienda/eliminar/<int:url_id>/', views.url_tienda_eliminar, name='url_tienda_eliminar'),
    path('admin/url-tienda/toggle/<int:url_id>/', views.url_tienda_toggle_activo, name='url_tienda_toggle_activo'),

    # Feed
    path('feed/', views.feed_view, name='feed'),
    path('post/<int:post_id>/like/', views.toggle_like_post_view, name='toggle_like'),
    path('api/post/<int:post_id>/comments/', get_comments_view, name='get_comments'),
    path('post/crear/', views.post_crear, name='post_crear'),
    path('post/<int:pk>/eliminar/', views.post_eliminar, name='post_eliminar'), 
    path('comentarios/crear/', views.comentario_crear, name='comentario_crear'),
    path('comentarios/<int:pk>/eliminar/', views.comentario_eliminar, name='comentario_eliminar'),
    

    # Chat HTML
    path('chat/room/<int:conversacion_id>/', views.chat_room, name='chat_room'),
    # Chat directo por username (una sola definición)
    path('chat/con/<str:username>/', views.chat_con_usuario, name='chat_con_usuario'),

    # Social (acciones web por username)
    path('amistad/enviar/<str:username>/', views.amistad_enviar, name='amistad_enviar'),
    path('amistad/aceptar/<str:username>/', views.amistad_aceptar, name='amistad_aceptar'),
    path('amistad/cancelar/<str:username>/', views.amistad_cancelar, name='amistad_cancelar'),

    # --- API REST (si las usas desde frontend) ---
    # Amistad
    path('api/amistad/solicitudes/', EnviarSolicitudAmistad.as_view(), name='api_amistad_enviar'),
    path('api/amistad/solicitudes/recibidas/', SolicitudesRecibidasList.as_view(), name='api_amistad_recibidas'),
    path('api/amistad/solicitudes/enviadas/', SolicitudesEnviadasList.as_view(), name='api_amistad_enviadas'),
    path('api/amistad/solicitudes/<int:pk>/aceptar/', AceptarSolicitud.as_view(), name='api_amistad_aceptar'),
    path('api/amistad/solicitudes/<int:pk>/rechazar/', RechazarSolicitud.as_view(), name='api_amistad_rechazar'),
    path('api/amistad/solicitudes/<int:pk>/cancelar/', CancelarSolicitud.as_view(), name='api_amistad_cancelar'),
    path('api/amistad/amigos/', AmigosList.as_view(), name='api_amigos_list'),
    path('api/amistad/amigos/<int:pk>/', EliminarAmigo.as_view(), name='api_amigos_eliminar'),

    # Chat API
    path('api/chat/conversaciones/', ConversacionesList.as_view(), name='conversaciones_list'),
    path('api/chat/conversaciones/<int:conv_id>/mensajes/', MensajesListCreate.as_view(), name='mensajes_list_create'),
    path('u/<str:username>/', views.perfil_publico, name='perfil_publico'),
    path("u/<str:username>/", views.perfil_publico, name="perfil_detalle"),

    path('', views.feed, name='feed'),
    path('comentarios/crear/', views.comentario_crear, name='comentario_crear'),
    path('comentarios/<int:pk>/eliminar/', views.comentario_eliminar, name='comentario_eliminar'),
    path('post/crear/', views.post_crear, name='post_crear'),

    # Favoritos (toggle)
    path('favoritos/toggle/<int:product_id>/', views.toggle_favorito, name='favoritos_toggle'),
    # Wishlist (acciones)
    path('wishlist/item/<int:item_id>/recibir/', views.wishlist_marcar_recibido, name='wishlist_marcar_recibido'),

    path('wishlist/item/<int:item_id>/desmarcar/',views.wishlist_desmarcar_recibido,name='wishlist_desmarcar_recibido'),
    path('amistad/amigos/', views.amistad_amigos_view, name='amistad_amigos'),
    path("chat/con-id/<str:username>/", views.conversacion_con_usuario_id, name="chat_con_usuario_id"),
    ###para el escribiendo:::
    path("api/chat/<int:conv_id>/typing/", views.TypingView.as_view(), name="chat_typing"),
    path("api/chat/typing/", views.TypingSummaryView.as_view(), name="chat_typing_summary"),

    ## Reseñas
    #path('resenas/', resenas_views.resenas_home, name='resenas_home'),
    #path('resenas/nueva/', resenas_views.crear_resena, name='resenas_nueva'),


    


]

# Archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Archivos estáticos (de la app)
urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)