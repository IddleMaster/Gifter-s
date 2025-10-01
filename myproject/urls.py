from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static
from django.conf import settings

from core import views  # vistas “normales” (templates)
# importa las vistas API que usas abajo
from core.views import (
    EnviarSolicitudAmistad, SolicitudesRecibidasList, SolicitudesEnviadasList,
    AceptarSolicitud, RechazarSolicitud, CancelarSolicitud,
    AmigosList, EliminarAmigo,
    ConversacionesList, MensajesListCreate,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),

    
    # Vistas estáticas (solo plantillas)
    path('', views.home, name='home'),
    path('login/', RedirectView.as_view(pattern_name='account_login', permanent=False), name='login'),
    path('register/', views.register_view, name='register'),
    path('service-details.html', TemplateView.as_view(template_name='service-details.html'), name='detallesServicio'),
    path('starter-page.html', TemplateView.as_view(template_name='starter-page.html'), name='StartPage'),
    path('ayuda.html', TemplateView.as_view(template_name='ayuda.html'), name='ayuda'),
    path('perfil/', views.profile_view, name='perfil'),
    path('perfil/editar/', views.profile_edit, name='perfil_editar'),


    
    # Vistas con lógica (funciones en views.py) ← NUEVAS
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email_view, name='verify_email'),
    #Productos
    path('productos/', views.productos_list, name='productos_list'),
    path('producto/<int:producto_id>/', views.producto_detalle, name='producto_detalle'),
    path('buscar/', views.buscar_productos, name='buscar_productos'),
    path('buscar-sugerencias/', views.buscar_sugerencias, name='buscar_sugerencias'),
    
    
    # Administración de productos (solo admin)
    path('admin/productos/', views.administrar_productos, name='administrar_productos'),
    path('admin/producto/crear/', views.producto_crear, name='producto_crear'),
    path('admin/producto/editar/<int:producto_id>/', views.producto_editar, name='producto_editar'),
    path('admin/producto/eliminar/<int:producto_id>/', views.producto_eliminar, name='producto_eliminar'),
    path('admin/producto/restaurar/<int:producto_id>/', views.producto_restaurar, name='producto_restaurar'),
    
    # URLs de tienda
    path('admin/url-tienda/eliminar/<int:url_id>/', views.url_tienda_eliminar, name='url_tienda_eliminar'),
    path('admin/url-tienda/toggle/<int:url_id>/', views.url_tienda_toggle_activo, name='url_tienda_toggle_activo'),
    #feed
    path('feed/', views.feed_view, name='feed'),
    path('post/<int:post_id>/like/', views.toggle_like_post_view, name='toggle_like'),
    #aqui termina el feed
    path('productos_list/', views.productos_list, name='productos_list'),
    path("chat/room/<int:conversacion_id>/", views.chat_room, name="chat_room"),
    
# Página de sala de chat (HTML) — usa conversacion_id
    path("chat/room/<int:conversacion_id>/", views.chat_room, name="chat_room"),

    # Amigos (API REST)
    path("amistad/solicitudes/", EnviarSolicitudAmistad.as_view()),
    path("amistad/solicitudes/recibidas/", SolicitudesRecibidasList.as_view()),
    path("amistad/solicitudes/enviadas/", SolicitudesEnviadasList.as_view()),
    path("amistad/solicitudes/<int:pk>/aceptar/", AceptarSolicitud.as_view()),
    path("amistad/solicitudes/<int:pk>/rechazar/", RechazarSolicitud.as_view()),
    path("amistad/solicitudes/<int:pk>/cancelar/", CancelarSolicitud.as_view()),
    path("amistad/amigos/", AmigosList.as_view()),
    path("amistad/amigos/<int:pk>/", EliminarAmigo.as_view()),

    # Chat (API REST)
    path("chat/conversaciones/", ConversacionesList.as_view(), name="conversaciones_list"),
    path("chat/conversaciones/<int:conv_id>/mensajes/", MensajesListCreate.as_view(), name="mensajes_list_create"),
]

# Esto es para los archivos que los usuarios suben (MEDIA)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# --- 2. AÑADE ESTA LÍNEA AL FINAL ---
# Esto es para los archivos de tu aplicación (CSS, JS, imágenes de la plantilla)
urlpatterns += staticfiles_urlpatterns()
    