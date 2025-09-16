
from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView
from core import views  # ← Importa tus vistas

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Vistas estáticas (solo plantillas)
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('login.html', TemplateView.as_view(template_name='login.html'), name='login'),
    path('register.html', TemplateView.as_view(template_name='register.html'), name='register'),
    path('service-details.html', TemplateView.as_view(template_name='service-details.html'), name='detallesServicio'),
    path('starter-page.html', TemplateView.as_view(template_name='starter-page.html'), name='StartPage'),
    path('ayuda.html', TemplateView.as_view(template_name='ayuda.html'), name='ayuda'),
    path('perfil.html', TemplateView.as_view(template_name='perfil.html'), name='perfil'),
    
    # Vistas con lógica (funciones en views.py) ← NUEVAS
    path('verification-sent/', views.verification_sent_view, name='verification_sent'),
    path('verify-email/<uuid:token>/', views.verify_email_view, name='verify_email'),
]