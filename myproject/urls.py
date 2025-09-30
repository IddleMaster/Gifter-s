
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView 
from core import views  # ← Importa tus vistas
from django.conf.urls.static import static
from django.conf import settings


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
    path('perfil.html', TemplateView.as_view(template_name='perfil.html'), name='perfil'),
    
    # Vistas con lógica (funciones en views.py) ← NUEVAS
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email_view, name='verify_email'),
    #Productos
    path('productos/', views.productos_list, name='productos_list'),
    path('producto/<int:producto_id>/', views.producto_detalle, name='producto_detalle'),
    path('buscar/', views.buscar_productos, name='buscar_productos'),
    
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
    path('productos_list/', views.productos_list, name='productos_list'),
    
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)