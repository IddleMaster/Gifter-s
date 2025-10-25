from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static as dj_static
from django.conf import settings
from core.views import *
from core import views
from django.contrib.auth import views as auth_views
from django.views.decorators.cache import never_cache


from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET
import json

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)







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
    path('ayuda/', views.ayuda_view, name='ayuda'),
    path("usuarios/", views.usuarios_list, name="usuarios_list"),
    path("buscar/", views.buscar_router, name="buscar_router"),
    path("producto/<int:id_producto>/", views.producto_detalle, name="producto_detalle"),

    
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
    path('api/post/<int:post_id>/comments/', views.get_comments_view, name='get_comments'),
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
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/admin/upload-csv/', views.upload_csv_view, name='api_upload_csv'),
    path('api/productos/', views.ProductoListAPIView.as_view(), name='api_producto_list'), 
    path('api/productos/<int:pk>/', views.ProductoDetailAPIView.as_view(), name='api_producto_detail'),
    # --- Rutas API para Reportes ---
    path('api/reports/products/download/', views.download_active_products_csv, name='api_report_products_download'), 
    
    # --- Rutas API para Usuarios (Admin) --- # <-- NUEVA SECCIÓN
    path('api/users/', views.UserListAPIView.as_view(), name='api_user_list'),
    path('api/users/<int:pk>/', views.UserDetailAPIView.as_view(), name='api_user_detail'),
    # Amistad
    path('api/amistad/solicitudes/', views.EnviarSolicitudAmistad.as_view(), name='api_amistad_enviar'),
    path('api/amistad/solicitudes/recibidas/', views.SolicitudesRecibidasList.as_view(), name='api_amistad_recibidas'),
    path('api/amistad/solicitudes/enviadas/', views.SolicitudesEnviadasList.as_view(), name='api_amistad_enviadas'),
    path('api/amistad/solicitudes/<int:pk>/aceptar/', views.AceptarSolicitud.as_view(), name='api_amistad_aceptar'),
    path('api/amistad/solicitudes/<int:pk>/rechazar/', views.RechazarSolicitud.as_view(), name='api_amistad_rechazar'),
    path('api/amistad/solicitudes/<int:pk>/cancelar/', views.CancelarSolicitud.as_view(), name='api_amistad_cancelar'),
    path('api/amistad/amigos/', views.AmigosList.as_view(), name='api_amigos_list'),
    path('api/amistad/amigos/<int:pk>/', views.EliminarAmigo.as_view(), name='api_amigos_eliminar'),
    path("amistad/eliminar/<str:username>/", views.amistad_eliminar, name="amistad_eliminar"),
    path("amistad/rechazar/<str:username>/", views.amistad_rechazar, name="amistad_rechazar"),

    # Chat API
    path('api/chat/conversaciones/', views.ConversacionesList.as_view(), name='conversaciones_list'),
    path('api/chat/conversaciones/<int:conv_id>/mensajes/', views.MensajesListCreate.as_view(), name='mensajes_list_create'),
    path("u/<str:username>/", views.perfil_publico, name="perfil_publico"),
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


    ##para el chat grupal:
    path('api/grupos/crear/', views.grupos_create, name='grupos_create'),
    path('api/conversaciones/<int:pk>/', views.conversacion_detalle, name='conversacion_detalle'),
    ##path("chat/typing/<int:conv_id>/", views.chat_typing, name="chat_typing"),
    ##path("chat/con-usuario/<str:username_or_id>/", views.chat_con_usuario_id, name="chat_con_usuario_id"),

    path('sugerencias-ia/<str:amigo_username>/', views.sugerencias_regalo_ia, name='sugerencias_regalo_ia'),


    path('grupos/<int:pk>/miembros/', views.grupos_members, name='grupos_members'),
    path('grupos/<int:pk>/agregar/', views.grupos_add_members, name='grupos_add_members'),
    path('grupos/<int:pk>/quitar/', views.grupos_remove_member, name='grupos_remove_member'),
    path('grupos/<int:pk>/eliminar/', views.grupos_delete, name='grupos_delete'),
    path('grupos/<int:pk>/leave/', views.grupos_leave, name='grupos_leave'),
    path('chat/<int:conv_id>/mark-read/', views.conversacion_mark_read, name='conversacion_mark_read'),
    path('chat/unread-summary/', views.chat_unread_summary, name='chat_unread_summary'),
    path("chat/unread-summary/", views.chat_unread_summary, name="chat_unread_summary"),
    path("chat/<int:conv_id>/mark-read/", views.conversacion_mark_read, name="conversacion_mark_read"),
 
   
    
    ##para resena jiji
    path("resena/", views.resena_sitio_crear, name="resena_sitio_crear"),
    path("resena/editar/", views.resena_sitio_editar, name="resena_sitio_editar"),
    path("resena/eliminar/", views.resena_sitio_eliminar, name="resena_sitio_eliminar"),




    # --- URLs PARA RESTABLECIMIENTO DE CONTRASEÑA (Flujo de Django) ---
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html', # Usa nuestra plantilla
             email_template_name='registration/password_reset_email.html', # Plantilla para el cuerpo del email
             subject_template_name='registration/password_reset_subject.txt', # Plantilla para el asunto
             success_url='/password_reset/done/' # A dónde ir tras enviar el form
         ),
         name='password_reset'), # <--- ESTE ES EL NOMBRE QUE BUSCA EL {% url %}
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html' # Usa nuestra plantilla de "enviado"
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html', # Usa nuestra plantilla para nueva contraseña
             success_url='/reset/done/' # A dónde ir tras cambiarla
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html' # Usa nuestra plantilla de "completado"
         ),
         name='password_reset_complete'),
    # --- Fin URLs para Restablecimiento ---

    

]

# Archivos estáticos de las apps
urlpatterns += staticfiles_urlpatterns()

# Media en desarrollo
if settings.DEBUG:
    urlpatterns += dj_static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

