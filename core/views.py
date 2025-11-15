from itertools import count
from django.templatetags.static import static
from django.shortcuts import render, redirect, get_object_or_404, resolve_url
from django.contrib.auth import login
from django.contrib import messages
from django.conf import settings
from core.services.gifter_ai import generar_sugerencias_regalo
from core.services.recommendations import recommend_when_wishlist_empty
from .forms import PostForm, RegisterForm, PerfilForm, PreferenciasUsuarioForm, EventoForm
from .models import *
from .models import Post, ReporteStrike
from django.apps import apps
from django.core.files.base import ContentFile
from .models import Mensaje, ParticipanteConversacion, Conversacion
from .services.recommendations import invalidate_user_reco_cache
from urllib.parse import unquote
from collections import deque
from core.services.profanity_filter import censurar_con_openai
from core.services.recommendations import recommend_products_for_user as ai_recommend_products
from core.services.social import amigos_qs, sugerencias_qs
from .emails import send_verification_email, send_welcome_email, send_report_email
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.urls import reverse
from django.db import IntegrityError, transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone


import uuid, base64
import requests
from django.shortcuts import get_object_or_404
from core.forms import ProfileEditForm
from .utils import get_default_wishlist, _push_inbox
import openai

from core.utils import get_default_wishlist
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import SolicitudAmistadSerializer, UsuarioLiteSerializer
from .serializers import *
from core.search import meili
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render  
from rest_framework.pagination import PageNumberPagination
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .serializers import ConversacionLiteSerializer, MensajeSerializer
import pandas as pd
import random
from core.services_social import amigos_qs, sugerencias_qs, obtener_o_crear_conv_directa
from django.contrib.auth import get_user_model
from django.utils.html import escape
from django.urls import reverse  
from django.views.decorators.http import require_GET
from django.core.cache import cache
# Para Reseña
from django.contrib import messages
from django.shortcuts import redirect
from .forms import ResenaSitioForm
#PDFS
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO

import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg, Count, Prefetch,Case,When,IntegerField
from django.core.files.storage import default_storage
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.utils.text import get_valid_filename
import os, uuid
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
import datetime
import csv

# Decoradores/permissions DRF
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser,IsAuthenticated, AllowAny

# Utilidades Django
from django.core.management import call_command
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
import hashlib
from django.db import transaction
from .models import Conversacion
from core.services.ai_recommender import rerank_products_with_embeddings
# Stdlib
from typing import List, Iterable

# Formularios locales (solo si tienes una vista de contacto que lo use)
from .forms import ContactForm
User = get_user_model()

from django.db.models.functions import Lower, Trim
##########
import logging
from django.db import connection
log = logging.getLogger("gifters.health")  # salus de los gifters
##########


#### notificaioens
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect,HttpRequest
from django.shortcuts import get_object_or_404, redirect
from .models import Notificacion
from django.db.models import Q
from .models import Notificacion


import os, json, requests
from urllib.parse import quote

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile

# Importa explícitamente el modelo (evita depender de import *)
from core.models import GeneratedCard, ProductoExterno, ProductoExternoFavorito

from django.http import Http404 
import traceback

from django.apps import apps 
from allauth.account.models import EmailAddress











from .models import Conversacion, ConversationEvent, SecretSantaAssignment

# Mínimo de participantes para que el sorteo sea interesante y aleatorio
# Se puede sobreescribir desde settings.py con SECRET_SANTA_MIN_PARTICIPANTS
MIN_SECRET_SANTA_PARTICIPANTS = getattr(settings, 'SECRET_SANTA_MIN_PARTICIPANTS', 4)

def _validate_participants_count(count: int, is_standalone: bool = False) -> tuple[bool, str]:
    """
    Valida que haya suficientes participantes para un sorteo.
    Args:
        count: Número de participantes únicos
        is_standalone: True si es un evento standalone (sin grupo asociado)
    Returns:
        (válido, mensaje de error) donde válido es True si hay suficientes participantes
    """
    if count < MIN_SECRET_SANTA_PARTICIPANTS:
        msg = f"Se necesitan al menos {MIN_SECRET_SANTA_PARTICIPANTS} participantes para generar un sorteo aleatorio interesante"
        return False, msg
    return True, ""
# Descubrir en runtime si existe EventParticipant
# === Modelos (autocarga por nombre de app y clase) ===
ConversationEvent = apps.get_model('core', 'ConversationEvent')
EventParticipant  = apps.get_model('core', 'EventParticipant')
SecretSantaAssignment = apps.get_model('core', 'SecretSantaAssignment')
# === Helper: existe el campo en el modelo? ===
def _field_exists(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False

# === Helper: derangement (nadie se asigna a sí mismo) ===
import random
def _derangement(users):
    """
    Genera una permutación donde nadie queda asignado a sí mismo (derangement).
    Usa el algoritmo de mezcla y verificación con múltiples intentos para garantizar 
    una buena aleatorización. Si falla después de muchos intentos, usa un método 
    determinístico de rotación que garantiza un resultado válido.
    
    Args:
        users: Lista de usuarios a permutar
        
    Returns:
        Lista permutada donde nadie queda en su posición original.
        None si hay menos de 2 usuarios.
    """
    n = len(users)
    if n < MIN_SECRET_SANTA_PARTICIPANTS:
        return None
        
    # Trabajamos con índices para evitar problemas con comparaciones de objetos
    idx = list(range(n))
    
    # Múltiples intentos con mezcla aleatoria (mejor distribución)
    for attempt in range(2000):  # Más intentos para mejor aleatorización
        perm = idx[:]
        for i in range(n - 1):  # Mezcla controlada
            j = random.randrange(i + 1, n)  # Solo intercambia con posiciones válidas
            perm[i], perm[j] = perm[j], perm[i]
            
        if all(i != j for i, j in zip(idx, perm)):
            return [users[i] for i in perm]
    
    # Fallback determinístico: rotación que garantiza que nadie queda en su posición
    # Solo se usa si los 2000 intentos aleatorios fallan (muy improbable con n>=4)
    rotated = [users[(i + 1) % n] for i in idx]
    return rotated

try:
    # Cambia 'core' si tu app de modelos se llama distinto
    EventParticipant = apps.get_model('core', 'EventParticipant')
    HAS_EVENT_PARTICIPANT = EventParticipant is not None
except Exception:
    EventParticipant = None
    HAS_EVENT_PARTICIPANT = False

if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
    # Intenta inicializar el cliente aquí para detectar errores de clave temprano
    try:
        openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        # Podrías hacer una llamada de prueba simple aquí si quieres verificar la clave
        print("[OpenAI] Cliente inicializado correctamente.")
    except Exception as e:
        print(f"¡ADVERTENCIA! Error al inicializar cliente OpenAI: {e}")
        openai_client = None # Define como None si falla
        openai.api_key = None # Mantén api_key compatible si usas código viejo
else:
    print("¡ADVERTENCIA! La variable OPENAI_API_KEY no está configurada.")
    openai_client = None
    openai.api_key = None

def usuarios_list(request):
    """
    Lista de usuarios que matchean la query en nombre / apellido / nombre_usuario / correo.
    Separa en: amigos (follow mutuo) y otros, usando _people_matches().
    Devuelve estructuras tipo 'card' que tu template usuarios_list.html ya espera:
    { id, nombre, username, avatar, url }
    """
    query = (request.GET.get("q") or "").strip()
    
    if query and request.user.is_authenticated:
         try:
             HistorialBusqueda.objects.create(
             id_user=request.user, 
             term=f"@{query}"
         )
         except Exception as e:
             print(f"Error al guardar historial de búsqueda de usuarios: {e}")

    # Si no hay query, mostramos vacío (o podrías redirigir a home si prefieres)
    if not query:
        context = {
            "query": "",
            "personas_amigos": [],
            "personas_otros": [],
        }
        return render(request, "usuarios_list.html", context)

    # Usa el helper que YA creaste con los campos correctos (nombre, apellido, nombre_usuario, correo)
    personas_amigos, personas_otros = _people_matches(
        request,
        query,
        limit_friends=24,
        limit_others=24,
    )

    context = {
        "query": query,
        "personas_amigos": personas_amigos,
        "personas_otros": personas_otros,
    }
    return render(request, "usuarios_list.html", context)
@login_required
def amistad_rechazar(request, username):
    """
    Rechaza una solicitud RECIBIDA (emisor = 'username', receptor = request.user).
    Responde JSON si es AJAX; si no, redirige con mensaje.
    """
    User = get_user_model()
    emisor = get_object_or_404(User, nombre_usuario=username)

    sol = get_object_or_404(
        SolicitudAmistad,
        emisor=emisor,
        receptor=request.user,
        estado=SolicitudAmistad.Estado.PENDIENTE,
    )

    sol.rechazar()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "username": emisor.nombre_usuario})

    messages.info(request, "Solicitud rechazada.")
    return redirect("perfil")

# === Helpers para pintar personas en resultados ===
def _avatar_abs(request, u):
    """Devuelve URL absoluta del avatar si existe."""
    try:
        pic = getattr(getattr(u, "perfil", None), "profile_picture", None)
        return request.build_absolute_uri(pic.url) if pic else None
    except Exception:
        return None
    
def buscar_router(request):
    """
    Decide si mandar a usuarios_list o a productos_list según la query.
    Reglas:
      1) Si empieza con @ -> usuarios
      2) Si solo hay matches en usuarios -> usuarios
      3) Si solo hay matches en productos -> productos
      4) Si hay en ambos -> productos (por defecto)
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        return redirect("productos_list")  # o a donde quieras por defecto

    # Fuerza explícita por prefijo
    if q.startswith("@"):
        return redirect(f"{reverse('usuarios_list')}?q={q.lstrip('@')}")

    # ¿Hay usuarios que coincidan?
    users_exists = User.objects.filter(
        is_active=True
    ).filter(
        Q(nombre__icontains=q) |
        Q(apellido__icontains=q) |
        Q(nombre_usuario__icontains=q) |
        Q(correo__icontains=q)
    ).exists()

    # ¿Hay productos que coincidan?
    prods_exists = Producto.objects.filter(
        activo=True
    ).filter(
        Q(nombre_producto__icontains=q) |
        Q(descripcion__icontains=q) |
        Q(id_marca__nombre_marca__icontains=q)
    ).exists()

    if users_exists and not prods_exists:
        return redirect(f"{reverse('usuarios_list')}?q={q}")
    if prods_exists and not users_exists:
        return redirect(f"{reverse('productos_list')}?q={q}")

    # Empate: por defecto productos. Cambia a usuarios_list si prefieres.
    return redirect(f"{reverse('productos_list')}?q={q}")

def _user_card_dict(request, u):
    nombre = f"{(u.nombre or '').strip()} {(u.apellido or '').strip()}".strip() or (u.nombre_usuario or '')
    username = u.nombre_usuario or ''
    return {
        "id": u.id,
        "nombre": nombre,
        "username": username,
        "avatar": _avatar_abs(request, u),
        # ajusta a tu URL real si usas otra ruta
        "url": f"/u/{username}/" if username else f"/perfil/{u.id}/",
    }

def _people_matches(request, query, limit_friends=8, limit_others=8):
    """
    Devuelve (amigos_cards, otros_cards) para una query.
    Amigos = follow mutuo (Seguidor).
    """
    if not query:
        return [], []

    # base de búsqueda
    base_q = (Q(nombre__icontains=query) |
              Q(apellido__icontains=query) |
              Q(nombre_usuario__icontains=query) |
              Q(correo__icontains=query))

    amigos_cards, otros_cards = [], []

    # si no está logueado, sólo “otros”
    if not request.user.is_authenticated:
        otros = (User.objects
                 .filter(is_active=True)
                 .exclude(id=request.user.id if request.user.is_authenticated else None)
                 .filter(base_q)
                 .select_related('perfil')
                 .order_by('nombre', 'apellido')[:limit_others])
        return [ ], [_user_card_dict(request, u) for u in otros]

    # ids amigos (follow mutuo)
    ids_yo_sigo   = Seguidor.objects.filter(seguidor=request.user).values_list('seguido_id', flat=True)
    ids_me_siguen = Seguidor.objects.filter(seguido=request.user).values_list('seguidor_id', flat=True)
    amigos_ids = set(ids_yo_sigo).intersection(set(ids_me_siguen))

    # amigos que matchean
    amigos = (User.objects
              .filter(id__in=amigos_ids, is_active=True)
              .filter(base_q)
              .select_related('perfil')
              .order_by('nombre', 'apellido')[:limit_friends])

    # otros usuarios
    otros = (User.objects
             .filter(is_active=True)
             .exclude(id__in=amigos_ids)
             .exclude(id=request.user.id)
             .filter(base_q)
             .select_related('perfil')
             .order_by('nombre', 'apellido')[:limit_others])

    amigos_cards = [_user_card_dict(request, u) for u in amigos]
    otros_cards  = [_user_card_dict(request, u) for u in otros]
    return amigos_cards, otros_cards



def home(request):
    is_admin_flag = request.user.is_authenticated and (request.user.is_staff or getattr(request.user, 'es_admin', False))

    # ===================== CATÁLOGO =====================
    try:
        productos_destacados = (
            Producto.objects.filter(activo=True).order_by('-fecha_creacion')[:9]
        )
    except Exception:
        productos_destacados = (
            Producto.objects.filter(activo=True).order_by('-pk')[:9]
        )

    # Categorías: intenta con distintos related_name
    categorias = []
    try:
        categorias = (Categoria.objects.filter(productos__activo=True).distinct().order_by('nombre_categoria')[:12])
    except Exception:
        try:
            categorias = (Categoria.objects.filter(producto__activo=True).distinct().order_by('nombre_categoria')[:12])
        except Exception:
            try:
                categorias = (Categoria.objects.filter(producto_set__activo=True).distinct().order_by('nombre_categoria')[:12])
            except Exception:
                categorias = []

    # ===================== SOCIAL =====================
    amigos = []
    sugerencias = []
    recibidas = []
    enviadas = []
    favoritos_ids_set = set()   # <-- set para lógica
    favoritos_ids_list = []     # <-- lista para template
    ai_reco = []

    if request.user.is_authenticated:
        # Amigos / sugerencias (no romper si falla)
        try:
            amigos = amigos_qs(request.user)
        except Exception:
            amigos = []

        try:
            sugerencias = sugerencias_qs(request.user, limit=9)
        except Exception:
            sugerencias = []

        try:
            recibidas = (
                SolicitudAmistad.objects
                .filter(receptor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE)
                .select_related('emisor')
                .order_by('-creada_en')[:10]
            )
            enviadas = (
                SolicitudAmistad.objects
                .filter(emisor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE)
                .select_related('receptor')
                .order_by('-creada_en')[:10]
            )
        except Exception:
            recibidas, enviadas = [], []

        # Wishlist / favoritos
        wl = None
        try:
            wl = get_default_wishlist(request.user)
            favoritos_ids_list = list(
                ItemEnWishlist.objects
                .filter(id_wishlist=wl)
                .values_list('id_producto', flat=True)
            )
            favoritos_ids_set = set(favoritos_ids_list)
        except Exception:
            favoritos_ids_list = []
            favoritos_ids_set = set()

        # --- 👇 PASO 1: OBTENER PRODUCTOS MARCADOS CON "NO ME GUSTA" 👇 ---
        try:
            disliked_product_ids = set(
                RecommendationFeedback.objects.filter(
                    user=request.user,
                    feedback_type='dislike'
                ).values_list('product_id', flat=True)
            )
        except Exception:
            disliked_product_ids = set()

        # --- PASO 2: CREAR UNA LISTA COMPLETA DE PRODUCTOS A EXCLUIR ---
        exclude_ids = favoritos_ids_set.union(disliked_product_ids)
        # -----------------------------------------------------------------

        # --- 👇 LÍNEA DE DEPURACIÓN CLAVE 👇 ---
        try:
            print(f"--- DEBUG HOME VIEW ---")
            print(f"Usuario: {getattr(request.user, 'nombre_usuario', request.user)}")
            print(f"IDs en Wishlist (Favoritos): {favoritos_ids_set}")
            print(f"IDs con Dislike: {disliked_product_ids}")
            print(f"Lista final de IDs a EXCLUIR: {exclude_ids}")
            print(f"----------------------")
        except Exception:
            pass

        # ===================== RECO (IA SOBRE CATÁLOGO) =====================
        try:
            ai_reco = ai_recommend_products(request.user, limit=6, exclude_ids=list(exclude_ids))
        except Exception:
            ai_reco = []

        # Fallback 1: por marcas de wishlist si vacío
        if not ai_reco:
            try:
                if wl is None:
                    wl = get_default_wishlist(request.user)
                wl_items = (
                    ItemEnWishlist.objects
                    .filter(id_wishlist=wl, fecha_comprado__isnull=True)
                    .select_related('id_producto', 'id_producto__id_marca')[:5]
                )
                marcas_ids = [
                    it.id_producto.id_marca_id
                    for it in wl_items
                    if it.id_producto and it.id_producto.id_marca_id
                ]
                qs = Producto.objects.filter(activo=True)
                if marcas_ids:
                    qs = qs.filter(id_marca_id__in=marcas_ids)

                ai_reco = list(
                    qs.exclude(pk__in=exclude_ids)
                      .order_by('-pk')[:6]
                )
            except Exception:
                ai_reco = []

        # Fallback 2: últimos del catálogo, excluyendo vistos
        if not ai_reco:
            try:
                ai_reco = list(
                    Producto.objects
                    .filter(activo=True)
                    .exclude(pk__in=exclude_ids)
                    .order_by('-pk')[:6]
                )
            except Exception:
                ai_reco = []
    else:
        ai_reco = []

    # ===================== RESEÑAS DEL SITIO =====================
    try:
        resenas_qs = (
            ResenaSitio.objects
            .select_related('id_usuario', 'id_usuario__perfil')
            .order_by('-fecha_resena')[:6]
        )
    except Exception:
        resenas_qs = []

    own_resena = None
    if request.user.is_authenticated:
        try:
            own_resena = (
                ResenaSitio.objects
                .filter(id_usuario=request.user)
                .order_by('-fecha_resena')
                .first()
            )
        except Exception:
            own_resena = None

    # --------- DEBUG útil en terminal ----------
    try:
        print("DEBUG home():",
              "destacados=", len(productos_destacados),
              "categorias=", len(categorias),
              "ai_reco=", len(ai_reco),
              "favoritos_ids=", len(favoritos_ids_list))
    except Exception:
        pass
    # ------------------------------------------

    context = {
        'productos_destacados': productos_destacados,
        'categorias': categorias,
        'amigos': amigos,
        'sugerencias': sugerencias,
        'solicitudes_recibidas': recibidas,
        'solicitudes_enviadas': enviadas,
        'favoritos_ids': favoritos_ids_list,  # <-- lista para el template (json_script)
        'resenas': resenas_qs,
        'own_resena': own_resena,
        'is_admin': is_admin_flag,
        'ai_reco': ai_reco,
    }
    return render(request, 'index.html', context)




def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    # Estado inicial: requiere verificación
                    user.is_active = False
                    user.is_verified = False
                    user.set_password(form.cleaned_data['password'])

                    # Asegurar token y timestamp
                    user.verification_token = user.verification_token or uuid.uuid4()
                    user.token_created_at = timezone.now()

                    user.save()

                # Intentar enviar email de verificación SIN borrar al usuario si falla
                try:
                    send_verification_email(user, request)
                    messages.success(
                        request,
                        '¡Cuenta creada! Te enviamos un email para verificar tu cuenta.'
                    )
                except Exception as e:
                    # No borramos el usuario; solo informamos el problema de correo
                    if settings.DEBUG:
                        messages.warning(
                            request,
                            f'Cuenta creada, pero falló el envío del correo de verificación: {e}'
                        )
                    else:
                        messages.warning(
                            request,
                            'Cuenta creada, pero no pudimos enviar el correo de verificación. '
                            'Intenta nuevamente más tarde.'
                        )

                return redirect('verification_sent')

            except IntegrityError:
                # Usualmente por correo o nombre_usuario duplicados
                messages.error(
                    request,
                    'Ese correo o nombre de usuario ya está registrado.'
                )
            except ValidationError as e:
                # Errores de validación a nivel modelo
                form.add_error(None, e)
            except Exception as e:
                if settings.DEBUG:
                    messages.error(request, f'Error inesperado al crear la cuenta: {e}')
                else:
                    messages.error(request, 'Error al crear la cuenta. Intenta nuevamente.')
        else:
            messages.error(request, 'Revisa los campos del formulario.')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})

def verification_sent_view(request):
    return render(request, 'verification_sent.html')

def verify_email_view(request, token):
    try:
        user = User.objects.get(verification_token=token)
        
        if user.is_verification_token_expired():
            messages.error(request, 'El enlace de verificación ha expirado.')
            return redirect('resend_verification')
        
        user.is_verified = True
        user.is_active = True
        user.verification_token = None
        user.save()
        
        # Enviar email de bienvenida
        send_welcome_email(user)
        
        messages.success(request, '¡Email verificado correctamente! Ya puedes iniciar sesión.')
        return redirect('login')
        
    except User.DoesNotExist:
        messages.error(request, 'El enlace de verificación no es válido.')
        return redirect('register')
    
def toggle_like_post(request, post_id):
    """Vista para alternar like en un post"""
    if request.method == 'POST':
        post = Post.objects.get(id_post=post_id)
        like_agregado = Like.toggle_like_post(request.user, post)
        
        # Obtener el nuevo conteo
        total_likes = Like.contar_likes_post(post)
        
        return JsonResponse({
            'success': True,
            'like_agregado': like_agregado,
            'total_likes': total_likes
        })

def obtener_info_likes_post(request, post_id):
    """Vista para obtener información de likes de un post"""
    post = Post.objects.get(id_post=post_id)
    
    total_likes = Like.contar_likes_post(post)
    usuario_dio_like = Like.usuario_dio_like_post(request.user, post) if request.user.is_authenticated else False
    
    return JsonResponse({
        'total_likes': total_likes,
        'usuario_dio_like': usuario_dio_like
    })
    

    
###PRODUCTOS
@login_required
@require_POST
def toggle_favorito(request, product_id):
    producto = get_object_or_404(Producto, pk=product_id, activo=True)
    wl = get_default_wishlist(request.user)

    item = ItemEnWishlist.objects.filter(id_wishlist=wl, id_producto=producto).first()
    if item:
        item.delete()
        state = "removed"
        # No registramos actividad al quitar de favoritos (puedes cambiar esto si quieres)
    else:
        # Requiere que ItemEnWishlist.cantidad use MinValueValidator(1)
        new_item = ItemEnWishlist.objects.create(id_wishlist=wl, id_producto=producto, cantidad=1) # Create the item
        state = "added"

        # --- MOVER EL REGISTRO DE ACTIVIDAD AQUÍ DENTRO ---
        try:
            RegistroActividad.objects.create(
                id_usuario=request.user,
                # Usamos 'NUEVO_REGALO' como aproximación a "intención de regalo"
                tipo_actividad=RegistroActividad.TipoActividad.NUEVO_REGALO,
                id_elemento=new_item.id_item, # Ahora 'new_item' SÍ existe en este scope
                tabla_elemento='itemenwishlist',
                contenido_resumen=f"Añadió '{producto.nombre_producto}' a favoritos"
            )
        except Exception as e:
            print(f"Error al guardar actividad (añadir favorito): {e}")
        # --- FIN DEL BLOQUE MOVIDO ---

    return JsonResponse({"status": "ok", "state": state, "product_id": product_id})

    
from django.db.models import Q
from django.core.paginator import Paginator

def productos_list(request):
    """Lista de productos internos + externos mezclados en una sola grilla."""

    query = (request.GET.get('q') or '').strip()
    categoria_id = (request.GET.get('categoria') or '').strip()
    marca_id = (request.GET.get('marca') or '').strip()
    orden = request.GET.get('orden', 'recientes')

    # === PRODUCTOS INTERNOS ===
    productos_internos = Producto.objects.filter(activo=True)

    # Filtros internos
    if query:
        productos_internos = productos_internos.filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(id_marca__nombre_marca__icontains=query)
        )
    if categoria_id:
        productos_internos = productos_internos.filter(id_categoria_id=categoria_id)
    if marca_id:
        productos_internos = productos_internos.filter(id_marca_id=marca_id)

    # Orden internos
    if orden == 'precio_asc':
        productos_internos = productos_internos.order_by('precio')
    elif orden == 'precio_desc':
        productos_internos = productos_internos.order_by('-precio')
    elif orden == 'nombre':
        productos_internos = productos_internos.order_by('nombre_producto')
    else:
        productos_internos = productos_internos.order_by('-fecha_creacion', '-id_producto')

    categorias = Categoria.objects.all()
    marcas = Marca.objects.all()

    # === WISHLIST ===
    favoritos_ids = set()
    favoritos_externos_ids = set()

    if request.user.is_authenticated:
        wl = get_default_wishlist(request.user)
        wishlist_items = ItemEnWishlist.objects.filter(id_wishlist=wl)

        favoritos_ids = set(
            wishlist_items.values_list('id_producto_id', flat=True)
        )

        favoritos_externos_ids = set(
            ProductoExterno.objects
            .filter(producto_interno_id__in=favoritos_ids)
            .values_list('id_producto_externo', flat=True)
        )

    # === PRODUCTOS EXTERNOS ===
    externos_qs = (
        ProductoExterno.objects
        .filter(imagen__isnull=False)
        .exclude(imagen="")
        .order_by('-fecha_extraccion')
    )

    if query:
        externos_qs = externos_qs.filter(
            Q(nombre__icontains=query) |
            Q(marca__icontains=query) |
            Q(categoria__icontains=query)
        )

    # Convertimos a lista
    productos_externos = list(externos_qs)

    # === UNIFICAR INTERNOS + EXTERNOS ===
    from itertools import chain

    # Los internos vienen como queryset → los externos como dict-like
    todos = list(chain(productos_internos, productos_externos))

    # === PAGINACIÓN COMBINADA ===
    paginator = Paginator(todos, 12)
    page_number = request.GET.get('page')
    productos = paginator.get_page(page_number)

    # === MATCH PERSONAS (no tocado) ===
    personas_amigos, personas_otros = _people_matches(request, query)

    # === HISTORIAL DE BÚSQUEDAS ===
    if query and request.user.is_authenticated:
        is_effective_search = Producto.objects.filter(
            activo=True
        ).filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(id_marca__nombre_marca__icontains=query)
        ).exists()

        if is_effective_search:
            try:
                HistorialBusqueda.objects.create(
                    id_user=request.user,
                    term=query
                )
            except Exception as e:
                print(f"Error al guardar historial de búsqueda: {e}")

    # === CONTEXT FINAL ===
    context = {
        'productos': productos,  # ← YA VIENE INTERNOS + EXTERNOS JUNTOS
        'categorias': categorias,
        'marcas': marcas,
        'query': query,
        'selected_categoria': categoria_id,
        'selected_marca': marca_id,
        'orden': orden,
        'favoritos_ids': favoritos_ids,
        'favoritos_externos_ids': favoritos_externos_ids,
        'personas_amigos': personas_amigos,
        'personas_otros': personas_otros,
        # YA NO SE USA productos_externos EN EL TEMPLATE
    }

    return render(request, 'productos_list.html', context)






def producto_detalle(request, producto_id):
    producto = get_object_or_404(Producto, id_producto=producto_id, activo=True)
    reseñas = []
    if hasattr(producto, 'resenas'):
        reseñas = producto.resenas.select_related('id_usuario').order_by('-fecha_resena')[:5]

    productos_similares = (Producto.objects
                           .filter(id_categoria=producto.id_categoria, activo=True)
                           .exclude(id_producto=producto_id)[:4])
    

    return render(request, 'productos/detalle.html', {
        'producto': producto,
        'reseñas': reseñas,
        'productos_similares': productos_similares,
    })


# Protege la página para que solo usuarios logueados puedan verla
## TODO LO QUE TENGA QUE VER CON EL FEED AQUI
@login_required
def feed_view(request):
    """
    Feed con soporte para posts de Texto / Imagen / GIF (GIPHY).
    """
    form = PostForm()

    if request.method == 'POST':
        # importante: incluir FILES para la imagen
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            nuevo_post = form.save(commit=False)
            nuevo_post.id_usuario = request.user

            # --- decidir tipo de post de forma segura ---
            gif_url = (request.POST.get('gif_url') or '').strip()
            has_image = bool(nuevo_post.imagen)
            has_text = bool((nuevo_post.contenido or '').strip())

            # prioridad: si hay GIF, es GIF (y anulamos imagen)
            if gif_url:
                nuevo_post.gif_url = gif_url
                nuevo_post.imagen = None
                nuevo_post.tipo_post = Post.TipoPost.GIF
            elif has_image:
                nuevo_post.gif_url = None
                nuevo_post.tipo_post = Post.TipoPost.IMAGEN
            elif has_text:
                nuevo_post.gif_url = None
                nuevo_post.tipo_post = Post.TipoPost.TEXTO
            else:
                # nada válido: vuelve con el form y un error simple
                form.add_error(None, "Debes escribir algo, subir una imagen o elegir un GIF.")
                # caerá al render de abajo con el error agregado

            if not form.errors:
                nuevo_post.save()
                return redirect('feed')

    # 1) Posts + likes optimizados
    try:
        ids_yo_sigo = set(Seguidor.objects.filter(seguidor=request.user).values_list('seguido_id', flat=True))
        ids_me_siguen = set(Seguidor.objects.filter(seguido=request.user).values_list('seguidor_id', flat=True))
        amigos_ids = ids_yo_sigo.intersection(ids_me_siguen)
        amigos_ids.add(request.user.id)
        all_posts = (
            Post.objects.filter(id_usuario_id__in=amigos_ids)
            .select_related('id_usuario')
            .prefetch_related('likes', 'comentarios__usuario__perfil')
            .order_by('-fecha_publicacion')
        )
    except Exception:
        all_posts = (
            Post.objects.all()
            .select_related('id_usuario')
            .prefetch_related('likes', 'comentarios__usuario__perfil')
            .order_by('-fecha_publicacion')
        )

    # 2) IDs con like del usuario
    liked_post_ids = set(
        Like.objects.filter(id_usuario=request.user, id_post__in=all_posts)
        .values_list('id_post_id', flat=True)
    )

    # 3) Flag para el template
    for post in all_posts:
        post.user_has_liked = post.id_post in liked_post_ids

    # 4) Leer toggle del filtro de malas palabras (?filtro_malas_palabras=1)
    usar_filtro = request.GET.get("filtro_malas_palabras") == "1"

    # 5) Generar versión censurada del contenido si aplica (POSTS)
    MAX_POSTS_AI = 15  # para no matar la API ni el tiempo de respuesta

    if usar_filtro:
        for idx, post in enumerate(all_posts):
            if idx < MAX_POSTS_AI:
                # asumimos que el texto está en post.contenido
                post.contenido_censurado = censurar_con_openai(post.contenido or "")
            else:
                # a partir del post 16, dejamos el contenido tal cual
                post.contenido_censurado = post.contenido
    else:
        for post in all_posts:
            post.contenido_censurado = None

    # 6) Generar versión censurada del contenido si aplica (COMENTARIOS DEL FEED)
    MAX_COMMENTS_AI = 40  # límite global

    if usar_filtro:
        censurados = 0
        for post in all_posts:
            for c in post.comentarios.all():
                if censurados < MAX_COMMENTS_AI:
                    c.contenido_censurado = censurar_con_openai(c.contenido or "")
                    censurados += 1
                else:
                    c.contenido_censurado = c.contenido
    else:
        for post in all_posts:
            for c in post.comentarios.all():
                c.contenido_censurado = None

    context = {
        'posts': all_posts,
        'form': form,
        'GIPHY_API_KEY': getattr(settings, 'GIPHY_API_KEY', ''),  # <-- para el buscador
        'usar_filtro': usar_filtro,
    }
    return render(request, 'feed.html', context)





@login_required
def toggle_like_post_view(request, post_id):
    """
    Vista para dar o quitar 'like' a un post.
    Responde con JSON para ser usada con JavaScript.
    """
    # Solo aceptamos peticiones POST para esta acción
    if request.method == 'POST':
        # Obtenemos el post, si no existe, devuelve un error 404
        post = get_object_or_404(Post, id_post=post_id)
        
        # Usamos el método que ya tienes en tu modelo Like. ¡Perfecto!
        like, created = Like.objects.get_or_create(id_usuario=request.user, id_post=post)

        # Si el like no fue creado, significa que ya existía, entonces lo borramos.
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        try:
                RegistroActividad.objects.create(
                    id_usuario=request.user,
                    tipo_actividad=RegistroActividad.TipoActividad.NUEVA_REACCION,
                    id_elemento=like.id_like, # O post.id_post si prefieres
                    tabla_elemento='like', # O 'post' si usas id_post
                    contenido_resumen=f"Le dio like al post {post.id_post}"
                )
        except Exception as e:
            print(f"Error al guardar actividad (nuevo like): {e}")    
        
            
        # Contamos el total de likes actual para el post
        total_likes = post.likes.count()
        
        # Devolvemos una respuesta en formato JSON
        return JsonResponse({'liked': liked, 'total_likes': total_likes})
    
    # Si no es una petición POST, devolvemos un error
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def get_comments_view(request, post_id):
    """
    Devuelve los datos de un post y sus comentarios en formato JSON.
    """
    post = get_object_or_404(Post, id_post=post_id)
    # Optimizamos la consulta para incluir el perfil del autor del comentario
    comentarios = Comentario.objects.filter(id_post=post).select_related('usuario__perfil').order_by('fecha_comentario')

    # Creamos una lista de diccionarios con los datos que necesitamos
    comentarios_data = []
    for comentario in comentarios:
        # Obtenemos la URL de la foto de perfil si existe
        autor_foto_url = None
        if hasattr(comentario.usuario, 'perfil') and comentario.usuario.perfil.profile_picture:
            autor_foto_url = comentario.usuario.perfil.profile_picture.url

        comentarios_data.append({
            'id': comentario.id_comentario,  # Añadimos el ID del comentario
            'autor': comentario.usuario.nombre_usuario,
            'contenido': comentario.contenido,
            'fecha': comentario.fecha_comentario.strftime('%d de %b, %Y a las %H:%M'),
            'autor_foto': autor_foto_url,
            'es_propietario': comentario.usuario.id == request.user.id # Flag para saber si el usuario actual es el dueño
        })
    
    # También preparamos los datos del post principal
    post_data = {
        'autor': post.id_usuario.nombre_usuario,
        'contenido': post.contenido,
        'fecha': post.fecha_publicacion.strftime('%d de %b, %Y a las %H:%M')
    }

    # Juntamos todo en un solo objeto para enviarlo
    data = {
        'post': post_data,
        'comentarios': comentarios_data
    }

    return JsonResponse(data)

@login_required
@require_POST
def post_eliminar(request, pk):
    """
    Vista para eliminar una publicación.
    """
    post = get_object_or_404(Post, pk=pk)
    # Solo el autor del post puede eliminarlo
    if post.id_usuario != request.user:
        return HttpResponseForbidden("No tienes permiso para eliminar esta publicación.")
    
    post.delete()
    messages.success(request, "Publicación eliminada correctamente.")
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'deleted_id': pk})
        
    return redirect(_next_url(request, default='/feed/'))

# FUNCIONES DE ADMINISTRACIÓN DE PRODUCTOS

def es_admin(user):
    """Verifica si el usuario es administrador"""
    return user.es_admin or user.is_staff

@login_required
@user_passes_test(es_admin)
def producto_crear(request):
    """Vista para crear nuevo producto"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            nombre_producto = request.POST.get('nombre_producto')
            descripcion = request.POST.get('descripcion')
            categoria_id = request.POST.get('categoria')
            marca_id = request.POST.get('marca')
            precio = request.POST.get('precio')
            imagen = request.FILES.get('imagen')
            
            # Validaciones básicas
            if not nombre_producto or not descripcion or not categoria_id or not marca_id:
                messages.error(request, 'Todos los campos obligatorios deben ser completados.')
                return redirect('producto_crear')
            
            categoria = get_object_or_404(Categoria, id_categoria=categoria_id)
            marca = get_object_or_404(Marca, id_marca=marca_id)
            
            # Crear producto
            producto = Producto.objects.create(
                nombre_producto=nombre_producto,
                descripcion=descripcion,
                id_categoria=categoria,
                id_marca=marca,
                precio=precio if precio else None,
                imagen=imagen
            )
            
            # Procesar URLs de tienda
            urls_tienda = request.POST.getlist('urls_tienda[]')
            nombres_tienda = request.POST.getlist('nombres_tienda[]')
            principales = request.POST.getlist('principales[]')
            
            for i, (url, nombre_tienda) in enumerate(zip(urls_tienda, nombres_tienda)):
                if url and nombre_tienda:
                    es_principal = str(i) in principales
                    UrlTienda.objects.create(
                        producto=producto,
                        url=url,
                        nombre_tienda=nombre_tienda,
                        es_principal=es_principal
                    )
            
            messages.success(request, f'Producto "{producto.nombre_producto}" creado exitosamente.')
            return redirect('producto_detalle', producto_id=producto.id_producto)
            
        except Exception as e:
            messages.error(request, f'Error al crear el producto: {str(e)}')
    
    # GET request - mostrar formulario
    categorias = Categoria.objects.all()
    marcas = Marca.objects.all()
    
    context = {
        'categorias': categorias,
        'marcas': marcas,
    }
    return render(request, 'productos/crear.html', context)

@login_required
@user_passes_test(es_admin)
def producto_editar(request, producto_id):
    """Vista para editar producto existente"""
    producto = get_object_or_404(Producto, id_producto=producto_id)
    
    if request.method == 'POST':
        try:
            # Actualizar datos del producto
            producto.nombre_producto = request.POST.get('nombre_producto')
            producto.descripcion = request.POST.get('descripcion')
            producto.id_categoria_id = request.POST.get('categoria')
            producto.id_marca_id = request.POST.get('marca')
            producto.precio = request.POST.get('precio') or None
            
            if 'imagen' in request.FILES:
                producto.imagen = request.FILES['imagen']
            
            producto.save()
            
            # Actualizar URLs existentes
            url_ids = request.POST.getlist('url_ids[]')
            urls_tienda = request.POST.getlist('urls_tienda[]')
            nombres_tienda = request.POST.getlist('nombres_tienda[]')
            principales = request.POST.getlist('principales[]')
            activos = request.POST.getlist('activos[]')
            
            # Actualizar URLs existentes
            for url_id, url, nombre_tienda in zip(url_ids, urls_tienda, nombres_tienda):
                if url_id:  # URL existente
                    url_obj = UrlTienda.objects.get(id_url=url_id, producto=producto)
                    url_obj.url = url
                    url_obj.nombre_tienda = nombre_tienda
                    url_obj.es_principal = url_id in principales
                    url_obj.activo = url_id in activos
                    url_obj.save()
                else:  # Nueva URL
                    if url and nombre_tienda:
                        UrlTienda.objects.create(
                            producto=producto,
                            url=url,
                            nombre_tienda=nombre_tienda,
                            es_principal=url_id in principales
                        )
            
            messages.success(request, f'Producto "{producto.nombre_producto}" actualizado exitosamente.')
            return redirect('producto_detalle', producto_id=producto.id_producto)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el producto: {str(e)}')
    
    # GET request - mostrar formulario de edición
    categorias = Categoria.objects.all()
    marcas = Marca.objects.all()
    urls_tienda = producto.urls_tienda.all()
    
    context = {
        'producto': producto,
        'categorias': categorias,
        'marcas': marcas,
        'urls_tienda': urls_tienda,
    }
    return render(request, 'productos/editar.html', context)

@login_required
@user_passes_test(es_admin)
def producto_eliminar(request, producto_id):
    """Vista para eliminar producto (soft delete)"""
    producto = get_object_or_404(Producto, id_producto=producto_id)
    
    if request.method == 'POST':
        producto.soft_delete()
        messages.success(request, f'Producto "{producto.nombre_producto}" eliminado correctamente')
        return redirect('productos_list')
    
    return render(request, 'productos/eliminar.html', {'producto': producto})

@login_required
@user_passes_test(es_admin)
def producto_restaurar(request, producto_id):
    """Vista para restaurar producto eliminado"""
    producto = get_object_or_404(Producto, id_producto=producto_id)
    
    if not producto.activo:
        producto.restaurar()
        messages.success(request, f'Producto "{producto.nombre_producto}" restaurado correctamente')
    
    return redirect('productos_list')

@login_required
@user_passes_test(es_admin)
def administrar_productos(request):
    """Vista para administrar todos los productos (incluyendo inactivos)"""
    query = request.GET.get('q', '')
    estado = request.GET.get('estado', 'activos')  # activos, inactivos, todos
    
    productos = Producto.objects.all()
    
    if query:
        productos = productos.filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(id_marca__nombre_marca__icontains=query)
        )
    
    if estado == 'activos':
        productos = productos.filter(activo=True)
    elif estado == 'inactivos':
        productos = productos.filter(activo=False)
    # 'todos' muestra ambos
    
    # Paginación
    paginator = Paginator(productos, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'productos': page_obj,
        'query': query,
        'estado': estado,
        'total_activos': Producto.objects.filter(activo=True).count(),
        'total_inactivos': Producto.objects.filter(activo=False).count(),
    }
    return render(request, 'productos/administrar.html', context)

# VISTAS PARA URLS DE TIENDA

@login_required
@user_passes_test(es_admin)
def url_tienda_eliminar(request, url_id):
    """Eliminar una URL de tienda específica"""
    url_tienda = get_object_or_404(UrlTienda, id_url=url_id)
    producto_id = url_tienda.producto.id_producto
    
    if request.method == 'POST':
        url_tienda.delete()
        messages.success(request, 'URL de tienda eliminada correctamente')
    
    return redirect('producto_editar', producto_id=producto_id)

@login_required
@user_passes_test(es_admin)
def url_tienda_toggle_activo(request, url_id):
    """Activar/desactivar una URL de tienda"""
    url_tienda = get_object_or_404(UrlTienda, id_url=url_id)
    producto_id = url_tienda.producto.id_producto
    
    url_tienda.activo = not url_tienda.activo
    url_tienda.save()
    
    estado = "activada" if url_tienda.activo else "desactivada"
    messages.success(request, f'URL {estado} correctamente')
    
    return redirect('producto_editar', producto_id=producto_id)

# VISTAS PARA BÚSQUEDA AVANZADA

def buscar_productos(request):
    """Búsqueda avanzada de productos (Meilisearch + fallback DB robusto, sin reseñas)"""
    # --- Params ---
    query = (request.GET.get('q') or '').strip()
    personas_amigos, personas_otros = _people_matches(request, query)
    categoria_id = (request.GET.get('categoria') or '').strip()
    marca_id = (request.GET.get('marca') or '').strip()
    precio_min = (request.GET.get('precio_min') or '').strip()
    precio_max = (request.GET.get('precio_max') or '').strip()
    rating_min = (request.GET.get('rating_min') or '').strip()  # <- por ahora se ignora
    orden = request.GET.get('orden', 'rating')
    per_page = 12
    try:
        page_number = int(request.GET.get('page') or 1)
        page_number = page_number if page_number > 0 else 1
    except ValueError:
        page_number = 1
        
    if query and request.user.is_authenticated:
        try:
            # Usamos update_or_create para no duplicar búsquedas idénticas muy seguidas
            # Podrías quitarlo si quieres CADA búsqueda individualmente
            HistorialBusqueda.objects.update_or_create(
                id_user=request.user, 
                term=query,
                defaults={'fecha_creacion': timezone.now()} # Actualiza la fecha si ya existía
            )
        except Exception as e:
            print(f"Error al guardar historial de búsqueda: {e}")

    def _ordenar_sin_rating(qs):
        """Ordenamiento cuando no hay relación de reseñas disponible."""
        if orden == 'precio_asc':
            return qs.order_by('precio')
        elif orden == 'precio_desc':
            return qs.order_by('-precio')
        elif orden == 'nombre':
            return qs.order_by('nombre_producto')
        else:
            # 'rating' o default -> usamos más recientes como aproximación
            return qs.order_by('-fecha_creacion', '-id_producto')

    def _filtrar_db_base(qs):
        """Filtros comunes en DB (sin rating)."""
        if query:
            qs = qs.filter(
                Q(nombre_producto__icontains=query) |
                Q(descripcion__icontains=query)
            )
        if categoria_id:
            qs = qs.filter(id_categoria_id=categoria_id)
        if marca_id:
            qs = qs.filter(id_marca_id=marca_id)
        if precio_min:
            try:
                qs = qs.filter(precio__gte=float(precio_min))
            except ValueError:
                pass
        if precio_max:
            try:
                qs = qs.filter(precio__lte=float(precio_max))
            except ValueError:
                pass
        # NOTE: rating_min se ignora hasta que exista relación de reseñas
        return qs

    def _render_db(productos_qs):
        productos_qs = _filtrar_db_base(productos_qs)
        productos_qs = _ordenar_sin_rating(productos_qs)

        paginator = Paginator(productos_qs, per_page)
        page_obj = paginator.get_page(page_number)

        categorias = Categoria.objects.all()
        marcas = Marca.objects.all()
        context = {
            'productos': page_obj,
            'categorias': categorias,
            'marcas': marcas,
            'query': query,
            'selected_categoria': categoria_id,
            'selected_marca': marca_id,
            'precio_min': precio_min,
            'precio_max': precio_max,
            'rating_min': rating_min,
            'orden': orden,
            'personas_amigos': personas_amigos,
            'personas_otros': personas_otros,

        }
        return render(request, 'productos/buscar.html', context)

    # ========== Fallback DB forzado ==========
    if not getattr(settings, "USE_MEILI", False):
        return _render_db(Producto.objects.filter(activo=True))

    # ========== Modo Meilisearch con try/except ==========
    # 1) Filtros Meili
    meili_filters = ["activo = true"]
    try:
        if categoria_id:
            meili_filters.append(f"id_categoria_id = {int(categoria_id)}")
        if marca_id:
            meili_filters.append(f"id_marca_id = {int(marca_id)}")
        if precio_min:
            meili_filters.append(f"precio >= {float(precio_min)}")
        if precio_max:
            meili_filters.append(f"precio <= {float(precio_max)}")
    except ValueError:
        pass
    filter_str = " AND ".join(meili_filters) if meili_filters else None

    # 2) Paginación/sort en Meili (precio adentro, otros afuera)
    offset = (page_number - 1) * per_page
    params = {"filter": filter_str, "offset": offset, "limit": per_page}
    if orden == 'precio_asc':
        params["sort"] = ["precio:asc"]
    elif orden == 'precio_desc':
        params["sort"] = ["precio:desc"]

    try:
        # 3) Buscar en Meili
        resp = meili().index("products").search(query or "", params)
        hits = resp.get("hits", [])
        total_hits = resp.get("estimatedTotalHits", resp.get("totalHits", 0))
        ids = [h.get("id") for h in hits if "id" in h]  # id_producto

        # 4) Traer desde DB y ordenar
        productos_qs = Producto.objects.filter(pk__in=ids)
        productos_qs = _filtrar_db_base(productos_qs)

        if orden in ('precio_asc', 'precio_desc', 'nombre'):
            productos_qs = _ordenar_sin_rating(productos_qs)
            productos_ordenados = list(productos_qs)
        elif orden == 'rating':
            # Sin reseñas: aproximamos con recientes
            productos_qs = productos_qs.order_by('-fecha_creacion', '-id_producto')
            productos_ordenados = list(productos_qs)
        else:
            # Mantener el orden de Meili (relevancia o precio ya aplicado)
            productos_map = {p.pk: p for p in productos_qs}
            productos_ordenados = [productos_map[i] for i in ids if i in productos_map]

        # 5) Page-like
        class _PageLike(list):
            def __init__(self, items, number, per_page, total):
                super().__init__(items)
                self.number = number
                self.paginator = type("P", (), {
                    "num_pages": (total + per_page - 1) // per_page,
                    "count": total,
                    "per_page": per_page
                })()

        page_obj = _PageLike(productos_ordenados, page_number, per_page, total_hits)

        categorias = Categoria.objects.all()
        marcas = Marca.objects.all()
        context = {
            'productos': page_obj,
            'categorias': categorias,
            'marcas': marcas,
            'query': query,
            'selected_categoria': categoria_id,
            'selected_marca': marca_id,
            'precio_min': precio_min,
            'precio_max': precio_max,
            'rating_min': rating_min,  # hoy se ignora
            'orden': orden,
        }
        return render(request, 'productos/buscar.html', context)

    except Exception:
        # Cualquier problema con Meili → fallback DB
        return _render_db(Producto.objects.filter(activo=True))

    # ========== Fallback DB forzado ==========
    if not getattr(settings, "USE_MEILI", False):
        return _render_db(Producto.objects.filter(activo=True))

    # ========== Modo Meilisearch con try/except ==========
    # 1) Filtros Meili
    meili_filters = ["activo = true"]
    try:
        if categoria_id:
            meili_filters.append(f"id_categoria_id = {int(categoria_id)}")
        if marca_id:
            meili_filters.append(f"id_marca_id = {int(marca_id)}")
        if precio_min:
            meili_filters.append(f"precio >= {float(precio_min)}")
        if precio_max:
            meili_filters.append(f"precio <= {float(precio_max)}")
    except ValueError:
        # Ignora parámetros no numéricos
        pass
    filter_str = " AND ".join(meili_filters) if meili_filters else None

    # 2) Paginación/sort en Meili (precio adentro, nombre/rating afuera)
    offset = (page_number - 1) * per_page
    params = {"filter": filter_str, "offset": offset, "limit": per_page}
    if orden == 'precio_asc':
        params["sort"] = ["precio:asc"]
    elif orden == 'precio_desc':
        params["sort"] = ["precio:desc"]

    try:
        # 3) Buscar en Meili
        resp = meili().index("products").search(query or "", params)
        hits = resp.get("hits", [])
        total_hits = resp.get("estimatedTotalHits", resp.get("totalHits", 0))
        ids = [h.get("id") for h in hits if "id" in h]  # id_producto

        # 4) Traer desde DB y ordenar / filtrar rating si aplica
        productos_qs = Producto.objects.filter(pk__in=ids)

        # rating_min también en modo Meili
        if rating_min:
            try:
                productos_qs = productos_qs.annotate(avg_rating=Avg('resenas__calificacion')) \
                                           .filter(avg_rating__gte=float(rating_min))
            except ValueError:
                productos_qs = productos_qs.annotate(avg_rating=Avg('resenas__calificacion'))

        if orden == 'nombre':
            productos_qs = productos_qs.order_by('nombre_producto')
            productos_ordenados = list(productos_qs)
        elif orden == 'rating':
            productos_qs = productos_qs.annotate(avg_rating=Avg('resenas__calificacion')) \
                                       .order_by('-avg_rating')
            productos_ordenados = list(productos_qs)
        else:
            # Mantener orden de Meili (relevancia o precio si fue seteado)
            productos_map = {p.pk: p for p in productos_qs}
            productos_ordenados = [productos_map[i] for i in ids if i in productos_map]

        # 5) Page-like
        class _PageLike(list):
            def __init__(self, items, number, per_page, total):
                super().__init__(items)
                self.number = number
                self.paginator = type("P", (), {
                    "num_pages": (total + per_page - 1) // per_page,
                    "count": total,
                    "per_page": per_page
                })()

        # Si aplicamos rating_min en DB, puede bajar la cuenta real de esta página;
        # mantenemos total_hits para no romper la UX de paginación.
        page_obj = _PageLike(productos_ordenados, page_number, per_page, total_hits)

        categorias = Categoria.objects.all()
        marcas = Marca.objects.all()
        context = {
            'productos': page_obj,
            'categorias': categorias,
            'marcas': marcas,
            'query': query,
            'selected_categoria': categoria_id,
            'selected_marca': marca_id,
            'precio_min': precio_min,
            'precio_max': precio_max,
            'rating_min': rating_min,
            'orden': orden,
        }
        return render(request, 'productos/buscar.html', context)

    except Exception:
       
        return _render_db(Producto.objects.filter(activo=True))



def _user_doc_to_sug(u):
    nombre = f"{(u.nombre or '').strip()} {(u.apellido or '').strip()}".strip() or (u.nombre_usuario or '')
    username = u.nombre_usuario or ''
    base_url = f"/u/{username}/" if username else f"/perfil/{u.id}/"
    # --- MODIFICACIÓN ---
    term_param = quote(f"{u.nombre} {u.apellido}".strip() or username) # Término a guardar
    final_url = f"{base_url}?from_suggestion=1&term={term_param}"
    return {
        "tipo": "usuario",
        "texto": nombre,
        "categoria": None,   # el front lo ignora si es None
        "marca": None,       # idem
        "url": f"/u/{username}/" if username else f"/perfil/{u.id}/",
        "meta": f"@{username}" if username else "",
    }

def buscar_sugerencias(request):
    """Sugerencias de búsqueda en tiempo real (Meilisearch + fallback DB)."""
    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'sugerencias': []})
        

    sugerencias = []


    # ======== Meilisearch ========
    if getattr(settings, "USE_MEILI", False):
        try:
            # --- Productos (igual que ya tenías) ---
            resp = meili().index("products").search(query, {
                "limit": 6,
                "attributesToRetrieve": ["id", "nombre_producto", "id_categoria_id", "id_marca_id"]
            })
            hits = resp.get("hits", [])
            ids = [h.get("id") for h in hits if "id" in h]
            productos = (Producto.objects
                         .filter(pk__in=ids, activo=True)
                         .select_related("id_categoria", "id_marca"))
            pmap = {p.pk: p for p in productos}
            for h in hits:
                p = pmap.get(h.get("id"))
                if not p: 
                    continue
                term_param_prod = quote(p.nombre_producto)
                prod_url = f"/producto/{p.id_producto}/?from_suggestion=1&term={term_param_prod}"
                sugerencias.append({
                    "tipo": "producto",
                    "texto": p.nombre_producto,
                    "marca": p.id_marca.nombre_marca if p.id_marca else "",
                    "categoria": p.id_categoria.nombre_categoria if p.id_categoria else "",
                    "url": prod_url
                })

            # --- USUARIOS en Meili ----
            uresp = meili().index("users").search(query, {
                "limit": 5,
                "filter": "is_active = true",
                "attributesToRetrieve": ["id", "nombre", "apellido", "nombre_usuario", "correo", "is_active"]
            })
            uids = [h.get("id") for h in uresp.get("hits", []) if "id" in h]
            # Traemos de DB para asegurar coherencia (por si cambió algo)
            umap = {u.id: u for u in User.objects.filter(id__in=uids, is_active=True)}
            for h in uresp.get("hits", []):
                u = umap.get(h.get("id"))
                if not u: 
                    continue
                sugerencias.append(_user_doc_to_sug(u))

            # --- Categorías / Marcas (DB) ---
            for c in Categoria.objects.filter(nombre_categoria__icontains=query)[:3]:
                term_param_cat = quote(c.nombre_categoria)
                cat_url = f"/productos/?categoria={c.id_categoria}&from_suggestion=1&term={term_param_cat}"
                sugerencias.append({
                    "tipo": "categoría",
                    "texto": c.nombre_categoria,
                    "descripcion": c.descripcion,
                    "url": f"/productos/?categoria={c.id_categoria}"
                })
            for m in Marca.objects.filter(nombre_marca__icontains=query)[:2]:
                
                term_param_marca = quote(m.nombre_marca)
                marca_url = f"/productos/?marca={m.id_marca}&from_suggestion=1&term={term_param_marca}"
                sugerencias.append({
                    "tipo": "marca",
                    "texto": m.nombre_marca,
                    "url": f"/productos/?marca={m.id_marca}"
                })
            
            return JsonResponse({'sugerencias': sugerencias})

        except Exception:
            # cae a fallback
            pass

    # ======== Fallback a DB ========
    # Productos
    productos = (Producto.objects
                 .filter(
                     Q(nombre_producto__icontains=query) |
                     Q(descripcion__icontains=query) |
                     Q(id_marca__nombre_marca__icontains=query),
                     activo=True
                 )
                 .select_related("id_categoria", "id_marca")[:6])
    for p in productos:
        sugerencias.append({
            "tipo": "producto",
            "texto": p.nombre_producto,
            "marca": p.id_marca.nombre_marca if p.id_marca else "",
            "categoria": p.id_categoria.nombre_categoria if p.id_categoria else "",
            "url": f"/producto/{p.id_producto}/"
        })

    # USUARIOS (DB)
    usuarios = (User.objects
                .filter(
                    Q(nombre__icontains=query) |
                    Q(apellido__icontains=query) |
                    Q(nombre_usuario__icontains=query) |
                    Q(correo__icontains=query),
                    is_active=True
                )
                .order_by('nombre', 'apellido')[:5])
    for u in usuarios:
        
        sugerencias.append(_user_doc_to_sug(u))

    # Categorías / Marcas
    for c in Categoria.objects.filter(nombre_categoria__icontains=query)[:3]:
        sugerencias.append({
            "tipo": "categoría",
            "texto": c.nombre_categoria,
            "descripcion": c.descripcion,
            "url": f"/productos/?categoria={c.id_categoria}"
        })
    for m in Marca.objects.filter(nombre_marca__icontains=query)[:2]:
        sugerencias.append({
            "tipo": "marca",
            "texto": m.nombre_marca,
            "url": f"/productos/?marca={m.id_marca}"
        })

    return JsonResponse({'sugerencias': sugerencias})



def login_view(request):
    """
    Login con email (correo) como username_field.
    Mantiene compatibilidad con AuthenticationForm y con tu botón de Google.
    """
    next_url = request.GET.get('next') or request.POST.get('next') or 'home'

    if request.method == 'POST':
        post_data = request.POST.copy()

        # Si tu template envía "correo" o "email", mapéalo a "username" que espera AuthenticationForm
        correo = (post_data.get('correo') or post_data.get('email') or post_data.get('username') or '').strip().lower()
        if correo:
            post_data['username'] = correo  # AuthenticationForm valida contra USERNAME_FIELD

        remember = bool(post_data.get('remember') or post_data.get('remember_me'))

        form = AuthenticationForm(request, data=post_data)
        if form.is_valid():
            user = form.get_user()  # ya autenticado por el form

            if not user.is_active:
                messages.error(request, 'Tu cuenta está desactivada.')
                return redirect('login')

            if hasattr(user, 'is_verified') and not user.is_verified:
                messages.error(request, 'Debes verificar tu correo antes de iniciar sesión.')
                request.session['pending_verify_email'] = correo
                return redirect('verification_sent')

            login(request, user)

            # “Recordarme”: si no está marcado, la sesión expira al cerrar el navegador
            if not remember:
                request.session.set_expiry(0)

            messages.success(request, f'¡Bienvenido {getattr(user, "nombre_usuario", user.correo)}!')
            return redirect(next_url)
        else:
            messages.error(request, 'Correo o contraseña inválidos.')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})

#def productos_list(request):
#    """Vista para listar todos los productos activos con filtros"""
#   query = request.GET.get('q', '')
#    categoria_id = request.GET.get('categoria', '')
#    marca_id = request.GET.get('marca', '')
#    
#    productos = Producto.objects.filter(activo=True)
#    
#    # Aplicar filtros
#    if query:
#        productos = productos.filter(
#            Q(nombre_producto__icontains=query) |
#            Q(descripcion__icontains=query) |
#            Q(id_marca__nombre_marca__icontains=query)
#        )
#    
#    if categoria_id:
#        productos = productos.filter(id_categoria_id=categoria_id)
#    
#    if marca_id:
#        productos = productos.filter(id_marca_id=marca_id)
#    
#    # Ordenar por fecha de creación (más recientes primero)
#    productos = productos.order_by('-fecha_creacion')
    
#    # Paginación
#    paginator = Paginator(productos, 12)  # 12 productos por página
#    page_number = request.GET.get('page')
#    page_obj = paginator.get_page(page_number)
#    
#    # Obtener todas las categorías y marcas para los filtros
#    categorias = Categoria.objects.all()
#    marcas = Marca.objects.all()
#    
#    context = {
#        'productos': page_obj,
#        'categorias': categorias,
#        'marcas': marcas,
#        'query': query,
#        'selected_categoria': categoria_id,
#        'selected_marca': marca_id,
#    }
#    return render(request, 'productos_list.html', context)  # ← CORREGIDO

@login_required
def profile_view(request):
    # --- Perfil + preferencias ---
    perfil, _ = Perfil.objects.get_or_create(user=request.user)
    prefs, _ = PreferenciasUsuario.objects.get_or_create(user=request.user)

    # --- Eventos del usuario ---
    eventos = (
        Evento.objects
        .filter(id_usuario=request.user)
        .order_by('fecha_evento', 'evento_id')
    )

    # Crear evento inline
    if request.method == 'POST' and request.POST.get('form') == 'evento':
        evento_form = EventoForm(request.POST)
        if evento_form.is_valid():
            ev = evento_form.save(commit=False)
            ev.id_usuario = request.user
            ev.save()
            messages.success(request, "Evento creado.")
            return redirect('perfil')
    else:
        evento_form = EventoForm()

    # ================== AMIGOS (seguimiento mutuo) ==================
    User = get_user_model()

    ids_yo_sigo = (
        Seguidor.objects
        .filter(seguidor=request.user)
        .values_list('seguido_id', flat=True)
    )
    ids_me_siguen = (
        Seguidor.objects
        .filter(seguido=request.user)
        .values_list('seguidor_id', flat=True)
    )

    ids_amigos = set(ids_yo_sigo).intersection(set(ids_me_siguen))

    amigos = (
        User.objects
        .filter(id__in=ids_amigos)
        .select_related('perfil')
        .order_by('nombre', 'apellido')
    )

    # ================== WISHLIST + RECIBIDOS ==================
    wl = get_default_wishlist(request.user)

    # Solo items NO recibidos (wishlist)
    wishlist_items = (
        ItemEnWishlist.objects
        .filter(
            id_wishlist=wl,
            fecha_comprado__isnull=True,   # en wishlist
        )
        .select_related('id_producto', 'id_producto__id_marca')
        # si tu related_name es distinto, ajusta esto
        .prefetch_related('id_producto__urls_tienda')
        .order_by('-id_item')
    )

    # Items ya recibidos (para pestaña "Regalos recibidos")
    recibidos_items = (
        ItemEnWishlist.objects
        .filter(
            id_wishlist=wl,
            fecha_comprado__isnull=False   # recibidos
        )
        .select_related('id_producto', 'id_producto__id_marca')
        .prefetch_related('id_producto__urls_tienda')
        .order_by('-fecha_comprado', '-id_item')
    )

    # IDs de productos que están en la wishlist (para pintar corazones)
    favoritos_ids = set(
        wishlist_items.values_list('id_producto_id', flat=True)
    )

    # ================== SOLICITUDES DE AMISTAD ==================
    solicitudes_recibidas = (
        SolicitudAmistad.objects
        .filter(
            receptor=request.user,
            estado=SolicitudAmistad.Estado.PENDIENTE
        )
        .select_related('emisor', 'emisor__perfil')
        .order_by('-creada_en')
    )

    solicitudes_enviadas = (
        SolicitudAmistad.objects
        .filter(
            emisor=request.user,
            estado=SolicitudAmistad.Estado.PENDIENTE
        )
        .select_related('receptor', 'receptor__perfil')
        .order_by('-creada_en')
    )

    sol_pendientes_count = solicitudes_recibidas.count()

    context = {
        'perfil': perfil,
        'prefs': prefs,
        'eventos': eventos,
        'evento_form': evento_form,

        # Amigos
        'amigos': amigos,

        # Wishlist / recibidos
        'wishlist_items': wishlist_items,
        'recibidos_items': recibidos_items,
        'favoritos_ids': favoritos_ids,

        # Solicitudes (nombres iguales a los que usa el template)
        'solicitudes_recibidas': solicitudes_recibidas,
        'solicitudes_enviadas': solicitudes_enviadas,
        'sol_pendientes_count': sol_pendientes_count,
    }
    return render(request, 'perfil.html', context)




@login_required
def profile_edit(request):
    user = request.user
    perfil, _ = Perfil.objects.get_or_create(user=user)
    prefs, _  = PreferenciasUsuario.objects.get_or_create(user=user)

    if request.method == 'POST':
        u_form    = ProfileEditForm(request.POST, instance=user)
        p_form    = PerfilForm(request.POST, request.FILES, instance=perfil)
        pref_form = PreferenciasUsuarioForm(request.POST, instance=prefs)

        if u_form.is_valid() and p_form.is_valid() and pref_form.is_valid():
            u_form.save()
            p_form.save()
            pref_form.save()

            # Guardamos la configuración de privacidad
            user.is_private = 'is_private' in request.POST
            user.save(update_fields=['is_private'])
            
            # --- 👇 NUEVA LÓGICA PARA GUARDAR INTERESES 👇 ---
            # Obtenemos las listas de IDs de los checkboxes marcados
            selected_category_ids = request.POST.getlist('intereses_categorias')
            selected_brand_ids = request.POST.getlist('intereses_marcas')

            # El método .set() es perfecto: limpia los intereses antiguos y añade los nuevos.
            user.intereses_categorias.set(selected_category_ids)
            user.intereses_marcas.set(selected_brand_ids)
            # ------------------------------------------------

            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('perfil')
        else:
            messages.error(request, 'Revisa los campos marcados.')
    else:
        # Si la petición es GET, preparamos los formularios como siempre
        u_form    = ProfileEditForm(instance=user)
        p_form    = PerfilForm(instance=perfil)
        pref_form = PreferenciasUsuarioForm(instance=prefs)

    # --- 👇 NUEVO CONTEXTO PARA MOSTRAR LAS OPCIONES 👇 ---
    # Obtenemos todas las categorías y marcas disponibles
    all_categories = Categoria.objects.all().order_by('nombre_categoria')
    all_brands = Marca.objects.all().order_by('nombre_marca')

    # Obtenemos los IDs de los intereses que el usuario ya tiene para marcar los checkboxes
    user_category_ids = set(user.intereses_categorias.values_list('id_categoria', flat=True))
    user_brand_ids = set(user.intereses_marcas.values_list('id_marca', flat=True))
    # ----------------------------------------------------

    return render(request, 'perfil_editar.html', {
        'u_form': u_form,
        'p_form': p_form,
        'pref_form': pref_form,
        # --- 👇 AÑADIMOS LAS NUEVAS VARIABLES AL CONTEXTO 👇 ---
        'all_categories': all_categories,
        'all_brands': all_brands,
        'user_category_ids': user_category_ids,
        'user_brand_ids': user_brand_ids,
    })


def chat_room(request, conversacion_id):
    conv = get_object_or_404(Conversacion, pk=conversacion_id)
    if not ParticipanteConversacion.objects.filter(conversacion=conv, usuario=request.user).exists():
        return HttpResponseForbidden("No eres participante de esta conversación.")

    # Asegúrate de que el perfil del usuario exista
    perfil, created = Perfil.objects.get_or_create(user=request.user)
    
    # Pasamos el usuario y su perfil al contexto de la plantilla
    return render(request, "chat/room.html", {
        "conversacion_id": conv.conversacion_id,
        "user": request.user,
        "user_perfil": perfil,
    })

    ##########   ##########   ##########   ##########   ##########   
  ##########   ##########     ##########   ##########   ##########   
  ########## SECCION DE LOS AMIGOS (solicitudes y demas) ###############   
  ##########   ##########   ##########   ##########   ##########   ## 
class IsAuthenticated(permissions.IsAuthenticated):
    pass

# POST /amistad/solicitudes/  (enviar)

@login_required
def evento_crear(request):
    if request.method != "POST":
        return redirect('perfil')
    form = EventoForm(request.POST)
    if form.is_valid():
        ev = form.save(commit=False)
        ev.id_usuario = request.user
        ev.save()
        messages.success(request, "Evento creado.")
    else:
        messages.error(request, "Revisa los campos del evento.")
    return redirect('perfil')

@login_required
def evento_editar(request, evento_id):
    ev = get_object_or_404(Evento, evento_id=evento_id, id_usuario=request.user)
    if request.method == "POST":
        form = EventoForm(request.POST, instance=ev)
        if form.is_valid():
            form.save()
            messages.success(request, "Evento actualizado.")
            return redirect('perfil')
        else:
            messages.error(request, "Revisa los campos del evento.")
    else:
        form = EventoForm(instance=ev)
    return render(request, 'perfil/evento_editar.html', {"form": form, "evento": ev})

@login_required
def evento_eliminar(request, evento_id):
    ev = get_object_or_404(Evento, evento_id=evento_id, id_usuario=request.user)
    if request.method == "POST":
        ev.delete()
        return redirect('perfil')
    return render(request, 'perfil/evento_eliminar.html', {"evento": ev})



class EnviarSolicitudAmistad(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        receptor_id = request.data.get("receptor_id")
        mensaje = request.data.get("mensaje", "")
        if not receptor_id:
            return Response({"detail": "receptor_id es requerido"}, status=400)
        if int(receptor_id) == request.user.id:
            return Response({"detail": "No puedes enviarte una solicitud a ti mismo."}, status=400)

        try:
            receptor = User.objects.get(pk=receptor_id)
        except User.DoesNotExist:
            return Response({"detail": "Usuario receptor no existe"}, status=404)

        try:
            with transaction.atomic():
                sol = SolicitudAmistad.objects.create(emisor=request.user, receptor=receptor, mensaje=mensaje)
        except IntegrityError:
            # UniqueConstraint emisor+receptor
            sol = SolicitudAmistad.objects.filter(emisor=request.user, receptor=receptor).first()

        return Response(SolicitudAmistadSerializer(sol).data, status=201)

# GET /amistad/solicitudes/recibidas/?estado=pendiente
class SolicitudesRecibidasList(generics.ListAPIView):
    serializer_class = SolicitudAmistadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        estado = self.request.query_params.get("estado")
        qs = SolicitudAmistad.objects.filter(receptor=self.request.user)
        if estado:
            qs = qs.filter(estado=estado)
        return qs.order_by("-creada_en")

# GET /amistad/solicitudes/enviadas/?estado=pendiente
class SolicitudesEnviadasList(generics.ListAPIView):
    serializer_class = SolicitudAmistadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        estado = self.request.query_params.get("estado")
        qs = SolicitudAmistad.objects.filter(emisor=self.request.user)
        if estado:
            qs = qs.filter(estado=estado)
        return qs.order_by("-creada_en")

# POST /amistad/solicitudes/{id}/aceptar
class AceptarSolicitud(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            sol = SolicitudAmistad.objects.get(pk=pk, receptor=request.user)
        except SolicitudAmistad.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada"}, status=404)
        conv = sol.aceptar()
        data = SolicitudAmistadSerializer(sol).data
        data["conversacion_id"] = getattr(conv, "conversacion_id", None)
        return Response(data)

@login_required
@require_POST
def amistad_eliminar(request, username):

    User = get_user_model()
    amigo = get_object_or_404(User, nombre_usuario=username)

    if amigo.id == request.user.id:
        return JsonResponse({"ok": False, "error": "no_self"}, status=400)

    # Quita seguimiento en ambos sentidos (tu modelo usa Seguidor)
    Seguidor.objects.filter(seguidor=request.user, seguido=amigo).delete()
    Seguidor.objects.filter(seguidor=amigo, seguido=request.user).delete()

    # Limpia solicitudes pendientes (cualquiera de las direcciones)
    SolicitudAmistad.objects.filter(
        Q(emisor=request.user, receptor=amigo) | Q(emisor=amigo, receptor=request.user),
        estado=SolicitudAmistad.Estado.PENDIENTE
    ).delete()

    # Respuesta AJAX
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "username": amigo.nombre_usuario})

    # Fallback no-AJAX
    messages.success(request, f"Dejaste de ser amigo de {amigo.nombre} {amigo.apellido}.")
    return redirect("perfil")

# POST /amistad/solicitudes/{id}/rechazar
class RechazarSolicitud(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            sol = SolicitudAmistad.objects.get(pk=pk, receptor=request.user)
        except SolicitudAmistad.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada"}, status=404)
        sol.rechazar()
        return Response(SolicitudAmistadSerializer(sol).data)


class CancelarSolicitud(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            sol = SolicitudAmistad.objects.get(pk=pk, emisor=request.user)
        except SolicitudAmistad.DoesNotExist:
            return Response({"detail": "Solicitud no encontrada"}, status=404)
        sol.cancelar()
        return Response(SolicitudAmistadSerializer(sol).data)

# GET /amistad/amigos/
class AmigosList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        amigos = request.user.amigos_qs
        return Response(UsuarioLiteSerializer(amigos, many=True).data)

# DELETE /amistad/amigos/{id}/  (dejar de ser amigos = remover follow mutuo)
class EliminarAmigo(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            amigo = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "Usuario no encontrado"}, status=404)

        Seguidor.objects.filter(seguidor=request.user, seguido=amigo).delete()
        Seguidor.objects.filter(seguidor=amigo, seguido=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


        ##############################
def _user_in_conversation(user, conversacion):
    return ParticipanteConversacion.objects.filter(conversacion=conversacion, usuario=user).exists()



class SmallPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100

class ConversacionesList(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = [IsAuthenticated]  # ✅ exige login

    def get(self, request):
        qs = (Conversacion.objects
              .filter(participantes__usuario=request.user)
              .select_related("ultimo_mensaje__remitente__perfil")
              .prefetch_related("participantes__usuario__perfil")
              .order_by("-actualizada_en")
              .distinct())

        # ✅ pasa request en context (evita 500 cuando el serializer lo necesita)
        data = ConversacionLiteSerializer(qs, many=True, context={"request": request}).data
        # === Inyectar unread_count por conversación (sin tocar el serializer) ===
        # Un no-leído = EntregaMensaje con estado ENTREGADO para este usuario, dentro de esa conversación
        from core.models import EntregaMensaje  # ya lo tienes en tu models.py

        # Creamos un índice para mutar rápido los dicts del serializer:
        conv_map = {c["conversacion_id"]: c for c in data}

        # Traemos counts agrupados por conversación:
        unread_qs = (EntregaMensaje.objects
                     .filter(usuario=request.user, estado=EntregaMensaje.Estado.ENTREGADO,
                             mensaje__conversacion__in=qs)
                     .values("mensaje__conversacion_id")
                     .annotate(cnt=Count("entrega_id")))

        for row in unread_qs:
            cid = row["mensaje__conversacion_id"]
            if cid in conv_map:
                conv_map[cid]["unread_count"] = row["cnt"]

        # Default en 0 si alguna conversación no vino en el QS de no leídos
        for c in data:
            if "unread_count" not in c:
                c["unread_count"] = 0

                # === Inyectar 'tipo' (y corregir is_group para EVENTO) ===
        # Mapeo rápido para recuperar tipo y un título de respaldo
        tipo_title_map = {
            c.conversacion_id: (
                str(getattr(c, "tipo", "")).lower(),
                (getattr(c, "titulo", None) or getattr(c, "nombre", None) or "")
            )
            for c in qs
        }

        for d in data:
            cid = d.get("conversacion_id")
            if cid in tipo_title_map:
                tipo_val, fallback_title = tipo_title_map[cid]
                if tipo_val:
                    d["tipo"] = tipo_val
                # Si es EVENTO, asegúrate que NO se marque como grupo
                if tipo_val == "evento":
                    d["is_group"] = False
                    if not d.get("titulo"):
                        d["titulo"] = fallback_title        

        return Response(data)


class MensajesListCreate(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = [IsAuthenticated]
    pagination_class = SmallPagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]   # <-- importante

    def get_conv(self, request, conv_id):
        try:
            return (Conversacion.objects
                    .prefetch_related("participantes__usuario__perfil")
                    .get(conversacion_id=conv_id, participantes__usuario=request.user))
        except Conversacion.DoesNotExist:
            return None

    def get(self, request, conv_id):
        conv = self.get_conv(request, conv_id)
        if not conv:
            return Response({"detail": "Conversación no encontrada"}, status=404)

        qs = (Mensaje.objects
              .filter(conversacion=conv)
              .select_related("remitente__perfil")
              .order_by("-creado_en"))

        paginator = SmallPagination()
        page = paginator.paginate_queryset(qs, request)
        ser = MensajeSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)


    def post(self, request, conv_id):
        conv = self.get_conv(request, conv_id)
        if not conv:
            return Response({"detail": "Conversación no encontrada"}, status=404)

        tipo = (request.data.get("tipo") or "texto").strip()
        contenido = (request.data.get("contenido") or "").strip()

        if tipo == Mensaje.Tipo.IMAGEN:
            up = request.FILES.get("archivo")
            if not up:
                return Response({"detail": "archivo es requerido"}, status=400)

            orig = get_valid_filename(up.name or "image")
            ext = os.path.splitext(orig)[1].lower() or ".jpg"
            name = f"chat/{uuid.uuid4().hex}{ext}"
            path = default_storage.save(name, up)
            url = default_storage.url(path)

            msg = Mensaje.objects.create(
                conversacion=conv,
                remitente=request.user,
                tipo=Mensaje.Tipo.IMAGEN,
                contenido=contenido,
                metadatos={"archivo_url": url},
            )
        else:
            if not contenido:
                return Response({"detail": "contenido es requerido"}, status=400)
            msg = Mensaje.objects.create(
                conversacion=conv,
                remitente=request.user,
                tipo=Mensaje.Tipo.TEXTO,
                contenido=contenido,
            )

        # puntero conversación
        conv.ultimo_mensaje = msg
        conv.save(update_fields=["ultimo_mensaje", "actualizada_en"])

        # entregas ENTREGADO (no el remitente)
        dest_ids = list(
            ParticipanteConversacion.objects
            .filter(conversacion=conv)
            .exclude(usuario=request.user)
            .values_list("usuario_id", flat=True)
        )
        if dest_ids:
            EntregaMensaje.objects.bulk_create([
                EntregaMensaje(mensaje=msg, usuario_id=uid, estado=EntregaMensaje.Estado.ENTREGADO)
                for uid in dest_ids
            ])
            _push_inbox(dest_ids, {
                "kind": "new_message",
                "conversacion_id": conv.conversacion_id,
                "mensaje_id": msg.mensaje_id,
            })

        return Response(MensajeSerializer(msg).data, status=201)



##nuevas funciones hoy 1 del 10 (abajo):
@login_required
def amistad_enviar(request, username):
    User = get_user_model()
    receptor = get_object_or_404(User, nombre_usuario=username)

    if receptor == request.user:
        msg = "No puedes enviarte una solicitud a ti mismo."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"ok": False, "detail": msg}, status=400)
        messages.warning(request, msg)
        return redirect('perfil_publico', username=username)

    # 1) Si el otro ya me envió una PENDIENTE → la aceptamos directo
    pendiente_recibida = SolicitudAmistad.objects.filter(
        emisor=receptor, receptor=request.user,
        estado=SolicitudAmistad.Estado.PENDIENTE
    ).first()
    if pendiente_recibida:
        conv = pendiente_recibida.aceptar()
        msg = f"¡Ahora eres amigo de {receptor.nombre}!"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"ok": True, "auto_accepted": True,
                                 "username": receptor.nombre_usuario,
                                 "conversacion_id": getattr(conv, "conversacion_id", None)})
        messages.success(request, msg)
        return redirect('perfil_publico', username=username)

    # 2) Si ya existe una solicitud mía → la reactivamos/actualizamos a PENDIENTE
    sol = SolicitudAmistad.objects.filter(
        emisor=request.user, receptor=receptor
    ).first()

    if sol:
        if sol.estado == SolicitudAmistad.Estado.PENDIENTE:
            msg = "Ya tienes una solicitud pendiente con este usuario."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"ok": True, "already_pending": True,
                                     "username": receptor.nombre_usuario})
            messages.info(request, msg)
            return redirect('perfil_publico', username=username)

        # reactivar (upsert)
        sol.estado = SolicitudAmistad.Estado.PENDIENTE
        sol.mensaje = ""
        sol.creada_en = timezone.now()
        sol.save(update_fields=["estado", "mensaje", "creada_en"])

        msg = f"Solicitud reenviada a {receptor.nombre}."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"ok": True, "reused": True,
                                 "username": receptor.nombre_usuario})
        messages.success(request, msg)
        return redirect('perfil_publico', username=username)

    # 3) No existe: crear normal
    try:
        with transaction.atomic():
            SolicitudAmistad.objects.create(
                emisor=request.user, receptor=receptor, mensaje=""
            )
    except IntegrityError:
        msg = "Ya existe una solicitud o relación con este usuario."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"ok": False, "detail": msg}, status=400)
        messages.info(request, msg)
        return redirect('perfil_publico', username=username)

    msg = f"Solicitud enviada a {receptor.nombre}."
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"ok": True, "created": True,
                             "username": receptor.nombre_usuario})
    messages.success(request, msg)
    return redirect('perfil_publico', username=username)



@login_required
def amistad_aceptar(request, username):
    User = get_user_model()
    emisor = get_object_or_404(User, nombre_usuario=username)
    sol = get_object_or_404(
        SolicitudAmistad,
        emisor=emisor,
        receptor=request.user,
        estado=SolicitudAmistad.Estado.PENDIENTE
    )
    conv = sol.aceptar()
    try:
        # Registrar que el receptor ahora sigue al emisor
        RegistroActividad.objects.create(
            id_usuario=request.user, # El que aceptó
            tipo_actividad=RegistroActividad.TipoActividad.NUEVO_SEGUIDOR,
            id_elemento=emisor.id, # A quién sigue
            tabla_elemento='user', # O 'seguidor' si prefieres
            contenido_resumen=f"Comenzó a seguir a {emisor.nombre_usuario}"
        )
        # Registrar que el emisor ahora sigue al receptor
        RegistroActividad.objects.create(
            id_usuario=emisor, # El que envió la solicitud
            tipo_actividad=RegistroActividad.TipoActividad.NUEVO_SEGUIDOR,
            id_elemento=request.user.id, # A quién sigue
            tabla_elemento='user',
            contenido_resumen=f"Comenzó a seguir a {request.user.nombre_usuario}"
        )
    except Exception as e:
        print(f"Error al guardar actividad (amistad aceptada): {e}")


    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            "ok": True,
            "username": emisor.nombre_usuario,
            "conversacion_id": getattr(conv, "conversacion_id", None)
        })

    messages.success(request, f"Ahora eres amigo de {emisor.nombre}.")
    if conv:
        return redirect('chat_room', conversacion_id=conv.conversacion_id)
    return redirect('home')


@login_required
def amistad_cancelar(request, username):
    User = get_user_model()
    receptor = get_object_or_404(User, nombre_usuario=username)
    sol = get_object_or_404(
        SolicitudAmistad,
        emisor=request.user,
        receptor=receptor,
        estado=SolicitudAmistad.Estado.PENDIENTE
    )
    sol.cancelar()

    # 👇 Responder JSON si es AJAX
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"ok": True, "username": receptor.nombre_usuario})

    messages.info(request, "Solicitud cancelada.")
    return redirect('home')


@login_required
def chat_con_usuario(request, username):
    User = get_user_model()
    other = get_object_or_404(User, nombre_usuario=username)
    conv = obtener_o_crear_conv_directa(request.user, other)  # por si entran desde “Amigos”
    return redirect('chat_room', conversacion_id=conv.conversacion_id)        


@login_required
def perfil_publico(request, username):
    usuario = get_object_or_404(User, nombre_usuario=username)

    # Si es tu propio perfil, redirige a la vista de perfil personal
    if request.user.is_authenticated and request.user.id == usuario.id:
        return redirect('perfil')

    perfil = getattr(usuario, 'perfil', None)

    es_amigo = False
    pendiente_enviada = None
    pendiente_recibida = None
    puede_chatear = False

    if request.user.is_authenticated:
        seguimientos = Seguidor.objects.filter(
            Q(seguidor=request.user, seguido=usuario) | Q(seguidor=usuario, seguido=request.user)
        ).values_list('seguidor_id', flat=True)
        sigo = request.user.id in seguimientos
        me_sigue = usuario.id in seguimientos
        es_amigo = sigo and me_sigue
        puede_chatear = es_amigo

        solicitudes = SolicitudAmistad.objects.filter(
            (Q(emisor=request.user, receptor=usuario) | Q(emisor=usuario, receptor=request.user)),
            estado=SolicitudAmistad.Estado.PENDIENTE
        )
        pendiente_enviada = solicitudes.filter(emisor=request.user).first()
        pendiente_recibida = solicitudes.filter(emisor=usuario).first()

    
    # Lógica de privacidad principal: si es privado y no son amigos, bloquea.
    if usuario.is_private and not es_amigo:
        context = {
            'usuario_publico': usuario,
            'perfil_publico': perfil,
            'es_amigo': es_amigo,
            'pendiente_enviada': pendiente_enviada,
            'pendiente_recibida': pendiente_recibida,
            'puede_chatear': puede_chatear,
        }
        return render(request, 'perfil_privado.html', context)

    # Si llegamos aquí, el visitante tiene permiso para ver el contenido.
    # Cargamos toda la información.

    eventos_publicos = Evento.objects.filter(id_usuario=usuario).order_by('fecha_evento')
    ultimos_posts = Post.objects.filter(id_usuario=usuario, es_publico=True).order_by('-fecha_publicacion')[:6]

    wl = Wishlist.objects.filter(usuario=usuario).first()
    wishlist_items_publicos = ItemEnWishlist.objects.none()
    recibidos_publicos = ItemEnWishlist.objects.none()
    sugerencias_ia_lista = []

    if wl:
        # Los regalos recibidos se cargan siempre si se tiene acceso al perfil.
        recibidos_publicos = (
            ItemEnWishlist.objects
            .filter(id_wishlist=wl, fecha_comprado__isnull=False)
            .select_related('id_producto', 'id_producto__id_marca')
            .prefetch_related(Prefetch('id_producto__urls_tienda',
                                       queryset=UrlTienda.objects.filter(activo=True)))
            .order_by('-fecha_comprado', '-pk')
        )

        # --- 👇 ESTA ES LA CORRECCIÓN 👇 ---
        # Se elimina la condición "if es_amigo". Ahora la wishlist se carga si el perfil es público
        # O si es privado y son amigos (porque ya pasamos el filtro de arriba).
        wishlist_items_publicos = (
            ItemEnWishlist.objects
            .filter(id_wishlist=wl, fecha_comprado__isnull=True)
            .select_related('id_producto', 'id_producto__id_marca')
            .prefetch_related(Prefetch('id_producto__urls_tienda',
                                       queryset=UrlTienda.objects.filter(activo=True)))
            .order_by('-pk')
        )

        # La lógica de IA ahora se ejecuta para amigos (en perfiles privados)
        # y para todos (en perfiles públicos).
        if es_amigo: # Mantenemos la IA solo para amigos para no gastar recursos innecesariamente
            nombres_wishlist = [
                it.id_producto.nombre_producto
                for it in wishlist_items_publicos[:5] if it.id_producto
            ]
            datos_para_ia = ""
            if nombres_wishlist:
                datos_para_ia = f"Artículos que tiene en su wishlist: {', '.join(nombres_wishlist)}.\n"
            else:
                nombres_recibidos = [
                    it.id_producto.nombre_producto
                    for it in recibidos_publicos[:5] if it.id_producto
                ]
                if nombres_recibidos:
                    datos_para_ia = f"Regalos que ha recibido antes: {', '.join(nombres_recibidos)}.\n"
                elif perfil and getattr(perfil, 'bio', ''):
                    datos_para_ia = f"Biografía: {perfil.bio}\n"
            
            if datos_para_ia:
                hctx = hashlib.sha1(datos_para_ia.encode('utf-8')).hexdigest()
                cache_key_ia = f"ia_text_user_{usuario.id}_{hctx}"
                sugerencias_ia_lista = cache.get(cache_key_ia, [])
                if not sugerencias_ia_lista:
                    try:
                        sugerencias_ia_lista = generar_sugerencias_regalo(usuario.nombre, datos_para_ia)
                    except Exception:
                        sugerencias_ia_lista = []
                    cache.set(cache_key_ia, sugerencias_ia_lista, 60 * 30)

    # Contexto final para la plantilla
    context = {
        'usuario_publico': usuario,
        'perfil_publico': perfil,
        'es_amigo': es_amigo,
        'pendiente_enviada': pendiente_enviada,
        'pendiente_recibida': pendiente_recibida,
        'puede_chatear': puede_chatear,
        'ultimos_posts': ultimos_posts,
        'eventos_publicos': eventos_publicos,
        'wishlist_items_publicos': wishlist_items_publicos,
        'recibidos_publicos': recibidos_publicos,
        'sugerencias_ia': sugerencias_ia_lista,
    }
    return render(request, 'perfil_publico.html', context)





def _next_url(request, default='/feed/'):
    # 1) usa 'next' del form si viene
    nxt = request.POST.get('next')
    if nxt:
        return nxt
    # 2) usa el referer si viene
    ref = request.META.get('HTTP_REFERER')
    if ref:
        return ref
    # 3) fallback duro al feed
    return default

@login_required
@require_POST
def post_crear(request):
    form = PostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.id_usuario = request.user
        if form.cleaned_data.get('imagen'):
             post.tipo_post = Post.TipoPost.IMAGEN
        else:
             post.tipo_post = Post.TipoPost.TEXTO
        post.save()
        messages.success(request, "¡Publicación creada con éxito!")

        # --- AÑADIR ESTO ---
        try:
            RegistroActividad.objects.create(
                id_usuario=request.user,
                tipo_actividad=RegistroActividad.TipoActividad.NUEVO_POST,
                id_elemento=post.id_post,
                tabla_elemento='post',
                contenido_resumen=f"Creó el post: {post.contenido[:50]}..." if post.contenido else "Creó un post con imagen."
            )
        except Exception as e:
            print(f"Error al guardar actividad (nuevo post): {e}")
        # --- FIN ---

    else:
        messages.error(request, "No se pudo crear la publicación. Revisa los datos.")
    return redirect(_next_url(request))

@login_required
def feed(request):
    # Si quieres súper simple: traes posts y el template usa post.comentarios.all
    posts = Post.objects.select_related('id_usuario__perfil').order_by('-fecha_publicacion')
    return render(request, 'feed/feed.html', {'posts': posts})

logger = logging.getLogger(__name__)


@login_required
@require_POST
def comentario_crear(request):
    post_id = request.POST.get('post_id')
    contenido = (request.POST.get('contenido') or '').strip()

    if not post_id or not contenido:
        # vuelve al feed (respetando ?next si viene)
        return redirect(_next_url(request))

    post = get_object_or_404(Post, pk=post_id)

    # Guardamos SIEMPRE el texto original
    c = Comentario.objects.create(
        id_post=post,
        usuario=request.user,
        contenido=contenido,
    )

    # Versión censurada
    try:
        contenido_censurado = censurar_con_openai(contenido)
    except Exception as e:
        print("[comentario_crear] Error al censurar:", e)
        contenido_censurado = contenido

    # Guardar también la versión censurada en la BD
    try:
        c.contenido_censurado = contenido_censurado
        c.save(update_fields=["contenido_censurado"])
    except Exception as e:
        print("[comentario_crear] Error al guardar contenido_censurado:", e)

    # Registro actividad
    try:
        RegistroActividad.objects.create(
            id_usuario=request.user,
            tipo_actividad=RegistroActividad.TipoActividad.NUEVO_COMENT,
            id_elemento=c.id_comentario,
            tabla_elemento='comentario',
            contenido_resumen=f"Comentó en el post {post_id}: {c.contenido[:50]}..."
        )
    except Exception as e:
        print(f"Error al guardar actividad (nuevo comentario): {e}")

    # AJAX → devolvemos JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        foto = getattr(getattr(request.user, 'perfil', None), 'profile_picture', None)
        return JsonResponse({
            'ok': True,
            'post_id': post.id_post,
            'comment': {
                'id': c.id_comentario,
                'nombre_usuario': request.user.nombre_usuario,
                'autor_foto': (foto.url if foto else None),
                'contenido': c.contenido,                     # original
                'contenido_censurado': contenido_censurado,   # filtrado
                'creado_en': c.fecha_comentario.strftime('%d %b, %Y %H:%M'),
            }
        })

    # Petición normal → redirect (con next)
    return redirect(_next_url(request))



@login_required
@require_POST
def comentario_eliminar(request, pk):
    c = get_object_or_404(Comentario, pk=pk)
    if c.usuario_id != request.user.id:
        return HttpResponseForbidden('No permitido')
    c.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'deleted_id': pk})
    return redirect(_next_url(request))

@login_required
@require_POST
def wishlist_marcar_recibido(request, item_id):
    wl = get_default_wishlist(request.user)
    item = get_object_or_404(ItemEnWishlist, id_wishlist=wl, pk=item_id)

    now = timezone.now()
    item.fecha_comprado = now
    item.save(update_fields=['fecha_comprado'])

    # Construir payload adicional para frontend
    producto = getattr(item, 'id_producto', None)
    product_info = None
    if producto:
        try:
            image_url = request.build_absolute_uri(producto.imagen.url) if getattr(producto, 'imagen', None) else None
        except Exception:
            image_url = None
        product_info = {
            'id': getattr(producto, 'id_producto', producto.pk if producto else None),
            'nombre': getattr(producto, 'nombre_producto', str(producto)),
            'image_url': image_url,
        }

    # fecha formateada para pintarla sin recargar
    fecha_text = now.strftime('%d/%m/%Y %H:%M')
    return JsonResponse({
        'ok': True,
        'item_id': item_id,
        'fecha': fecha_text,
        # Indicadores para el frontend: mostrar botón "Agradecer" sin recargar
        'can_thank': True,
        'product': product_info,
    })


@login_required
@require_POST
def wishlist_desmarcar_recibido(request, item_id):
    wl = get_default_wishlist(request.user)
    item = get_object_or_404(ItemEnWishlist, id_wishlist=wl, pk=item_id)

    item.fecha_comprado = None
    item.save(update_fields=['fecha_comprado'])

    return JsonResponse({'ok': True, 'item_id': item_id})

@login_required
def amistad_amigos_view(request):
    """
    Devuelve la lista de amigos del usuario autenticado.
    - Si el User no tiene .amigos_qs, usa core.services_social.amigos_qs(user).
    - Incluye nombre_usuario, nombre(s), apellido(s), nombre_completo y avatar absoluto si existe.
    """
    try:
        try:
            amigos_qs = request.user.amigos_qs
        except AttributeError:
            from core.services.social import amigos_qs as amigos_func  # ← con punto, no con guion bajo
            amigos_qs = amigos_func(request.user)

        amigos_qs = amigos_qs.select_related('perfil')

        data = []
        for u in amigos_qs:
            nombre_completo = f"{(u.nombre or '').strip()} {(u.apellido or '').strip()}".strip() or (u.nombre_usuario or "")
            avatar_url = None
            try:
                if getattr(u, 'perfil', None) and getattr(u.perfil, 'profile_picture', None):
                    # URL absoluta para que el front pueda usarla directo en <img>
                    avatar_url = request.build_absolute_uri(u.perfil.profile_picture.url)
            except Exception:
                avatar_url = None

            data.append({
                "id": u.id,
                "nombre_usuario": u.nombre_usuario or "",
                "nombre": u.nombre or "",
                "apellido": u.apellido or "",
                "nombre_completo": nombre_completo,
                "perfil": {"profile_picture_url": avatar_url},
            })

        return JsonResponse(data, safe=False, status=200)

    except Exception as e:
        # Devuelve un JSON claro para que puedas ver el motivo en red si algo falla
        return JsonResponse({"detail": "error_listando_amigos", "error": str(e)}, status=500)


@login_required
@require_GET
def conversacion_con_usuario_id(request, username):
    User = get_user_model()
    other = get_object_or_404(User, nombre_usuario=username)
    conv = obtener_o_crear_conv_directa(request.user, other)
    return JsonResponse({"conversacion_id": conv.conversacion_id})       



#### para que salga el escribiendo...
class TypingView(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = [IsAuthenticated]

    def _conv_for(self, request, conv_id):
        try:
            return (Conversacion.objects
                    .prefetch_related("participantes__usuario")
                    .get(conversacion_id=conv_id,
                         participantes__usuario=request.user))
        except Conversacion.DoesNotExist:
            return None

    def post(self, request, conv_id):
        """
        Marca 'typing' del usuario en esta conversación.
        Body JSON: {"typing": true/false}
        Guarda en cache por 5s.
        """
        conv = self._conv_for(request, conv_id)
        if not conv:
            return Response({"detail": "Conversación no encontrada"}, status=404)

        typing = bool(request.data.get("typing"))
        key = f"chat:typing:{conv_id}:{request.user.id}"
        if typing:
            # TTL corto; mientras el cliente renueve, se mantiene
            cache.set(key, 1, timeout=5)
        else:
            cache.delete(key)
        return Response({"ok": True})

    def get(self, request, conv_id):
        """
        Devuelve lista de usuarios (otros) que están escribiendo ahora.
        """
        conv = self._conv_for(request, conv_id)
        if not conv:
            return Response({"detail": "Conversación no encontrada"}, status=404)

        typing_users = []
        for p in conv.participantes.all():
            u = p.usuario
            if u.id == request.user.id:
                continue
            key = f"chat:typing:{conv_id}:{u.id}"
            if cache.get(key):
                typing_users.append({
                    "id": u.id,
                    "username": getattr(u, "nombre_usuario", "") or getattr(u, "username", ""),
                    "nombre": (getattr(u, "nombre", "") or "") + " " + (getattr(u, "apellido", "") or "")
                })

        return Response({"typing": typing_users})
class TypingSummaryView(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Todas mis conversaciones
        convs = (Conversacion.objects
                 .filter(participantes__usuario=request.user)
                 .prefetch_related("participantes__usuario")
                 .distinct())

        result = {}
        for conv in convs:
            typing_users = []
            for p in conv.participantes.all():
                u = p.usuario
                if u.id == request.user.id:
                    continue
                key = f"chat:typing:{conv.conversacion_id}:{u.id}"
                if cache.get(key):
                    typing_users.append({
                        "id": u.id,
                        "username": getattr(u, "nombre_usuario", "") or getattr(u, "username", ""),
                        "nombre": f"{getattr(u,'nombre','') or ''} {getattr(u,'apellido','') or ''}".strip()
                    })
            if typing_users:
                result[str(conv.conversacion_id)] = typing_users

        return Response({"typing": result})        


@login_required
@require_POST
def resena_sitio_crear(request):
    # Bloquea duplicados (pide usar editar)
    if ResenaSitio.objects.filter(id_usuario=request.user).exists():
        messages.warning(request, "Ya tienes una reseña. Usa el botón Editar para actualizarla.")
        return redirect(f"{reverse('home')}#testimonials")  # vuelve al bloque de reseñas

    form = ResenaSitioForm(request.POST)
    if form.is_valid():
        try:
            r = form.save(commit=False)
            r.id_usuario = request.user
            r.save()
            messages.success(request, "¡Gracias por tu reseña!")
        except IntegrityError:
            # Por si luego agregas UniqueConstraint en BD
            messages.warning(request, "Ya tienes una reseña. Usa Editar para actualizarla.")
    else:
        messages.error(request, "Revisa la calificación (1–5) y/o tu comentario.")
    return redirect(f"{reverse('home')}#testimonials")


@login_required
def resena_sitio_editar(request):
    if request.method != "POST":
        return redirect(f"{reverse('home')}#testimonials")

    instancia = ResenaSitio.objects.filter(id_usuario=request.user).first()
    if not instancia:
        messages.warning(request, "Aún no tienes reseña para editar.")
        return redirect(f"{reverse('home')}#testimonials")

    form = ResenaSitioForm(request.POST, instance=instancia)
    if form.is_valid():
        form.save()
        messages.success(request, "¡Actualizamos tu reseña! ✨")
    else:
        messages.error(request, "Revisa la calificación (1–5) y/o tu comentario.")
    return redirect(f"{reverse('home')}#testimonials")


@login_required
@require_POST
def resena_sitio_eliminar(request):
    instancia = ResenaSitio.objects.filter(id_usuario=request.user).first()
    if not instancia:
        messages.warning(request, "No tienes reseña para eliminar.")
        return redirect(f"{reverse('home')}#testimonials")

    instancia.delete()
    messages.success(request, "Reseña eliminada.")
    return redirect(f"{reverse('home')}#testimonials")




### CHAT GRUPALLLL


def _participant_dict(u: User):
    """Estructura que tu front ya consume."""
    nombre = getattr(u, 'nombre', '') or ''
    apellido = getattr(u, 'apellido', '') or ''
    nombre_completo = getattr(u, 'nombre_completo', '') or (f"{nombre} {apellido}".strip() or u.get_full_name() or u.username)
    return {
        "id": u.id,
        "username": getattr(u, 'username', '') or getattr(u, 'nombre_usuario', ''),
        "nombre": nombre,
        "apellido": apellido,
        "nombre_completo": nombre_completo,
        # intenta varias propiedades típicas de foto
        "avatar_url": (
            getattr(u, 'avatar_url', None)
            or getattr(u, 'avatar', None)
            or getattr(getattr(u, 'perfil', None) or {}, 'foto_url', None)
        ),
    }

@login_required
@require_http_methods(["POST"])
def grupos_create(request):
    try:
        raw = request.body.decode("utf-8")
        print("grupos_create RAW:", raw)  # LOG
        data = json.loads(raw)
    except Exception as e:
        print("grupos_create JSON inválido:", e)  # LOG
        return HttpResponseBadRequest("JSON inválido")

    titulo = (data.get("titulo") or "").strip()
    miembros = data.get("miembros") or data.get("ids") or []

    print("grupos_create titulo:", titulo, "miembros:", miembros)  # LOG

    if not titulo:
        return JsonResponse({"detail": "Falta 'titulo'"}, status=400)

    try:
        miembros = [int(x) for x in miembros]
    except Exception:
        return JsonResponse({"detail": "'miembros'/'ids' debe ser lista de enteros"}, status=400)

    if request.user.id not in miembros:
        miembros.append(request.user.id)

    users = list(User.objects.filter(id__in=miembros).distinct())
    if len(users) < 2:
        return JsonResponse({"detail": "Un grupo debe tener al menos 2 miembros"}, status=400)

    try:
        with transaction.atomic():
            conv = Conversacion.objects.create(
                tipo=Conversacion.Tipo.GRUPO,
                nombre=titulo,
                creador=request.user
            )
            ParticipanteConversacion.objects.bulk_create([
                ParticipanteConversacion(
                    conversacion=conv,
                    usuario=u,
                    rol=(ParticipanteConversacion.Rol.ADMIN if u.id == request.user.id
                         else ParticipanteConversacion.Rol.MIEMBRO)
                ) for u in users
            ])
        print("grupos_create OK:", conv.conversacion_id)  # LOG
        return JsonResponse({"ok": True, "conversacion_id": conv.conversacion_id})
    except Exception as e:
        import traceback
        print("grupos_create ERROR:", e)
        traceback.print_exc()
        return JsonResponse({"detail": "grupos_create_failed", "error": str(e)}, status=500)
    
@login_required
@require_http_methods(["GET"])
def conversacion_detalle(request, pk: int):
    conv = get_object_or_404(Conversacion, conversacion_id=pk)

    if not ParticipanteConversacion.objects.filter(conversacion=conv, usuario=request.user).exists():
        return HttpResponseForbidden("No tienes acceso a esta conversación")

    participantes_qs = User.objects.filter(
        id__in=ParticipanteConversacion.objects.filter(conversacion=conv).values_list("usuario_id", flat=True)
    ).select_related("perfil")

    def abs_avatar(u):
        try:
            pic = getattr(getattr(u, "perfil", None), "profile_picture", None)
            if pic:
                return request.build_absolute_uri(pic.url)
        except Exception:
            pass
        return None

    data_part = []
    for u in participantes_qs:
        nombre = (u.nombre or "").strip()
        apellido = (u.apellido or "").strip()
        nombre_completo = (f"{nombre} {apellido}".strip()
                           or getattr(u, "nombre_completo", "")
                           or getattr(u, "get_full_name", lambda: "")()
                           or getattr(u, "nombre_usuario", "")
                           or getattr(u, "username", ""))
        data_part.append({
            "id": u.id,
            "username": getattr(u, "nombre_usuario", "") or getattr(u, "username", ""),
            "nombre": nombre,
            "apellido": apellido,
            "nombre_completo": nombre_completo,
            "avatar_url": abs_avatar(u),
        })

    # --- NUEVO: normalizar tipo ('evento' / 'grupo' / 'privado' ...)
    def _tipo_str(val):
        if hasattr(val, "name"):       # Enum (Choices)
            return val.name.lower()
        s = str(val or "")
        return s.lower().split(".")[-1]

    tipo_norm = _tipo_str(getattr(conv, "tipo", ""))

    # usa 'titulo' si existe, si no 'nombre'
    title = (getattr(conv, "titulo", None) or getattr(conv, "nombre", None) or "")

    # deduce grupo por tipo o por cantidad de participantes
    is_group = bool(
        getattr(conv, "is_group", False) or
        (tipo_norm == "grupo") or
        (len(data_part) > 2)
    )
    # si es EVENTO, NO se trata como grupo para el UI
    if tipo_norm == "evento":
        is_group = False

    # --- NUEVO: empaquetar datos del evento (id/estado) si la conv es de evento
    evento_obj = None
    try:
        evento = ConversationEvent.objects.select_related("conversacion").filter(conversacion=conv).first()
        if evento:
            evento_obj = {
                "id": evento.id,
                "estado": getattr(evento, "estado", "") or "",
            }
    except Exception:
        evento_obj = None

    return JsonResponse({
        "conversacion_id": getattr(conv, "conversacion_id", conv.pk),
        "is_group": is_group,
        "titulo": title,
        "tipo": tipo_norm,          # ← NUEVO
        "evento": evento_obj,       # ← NUEVO (tu JS lo usa para mostrar el botón)
        "participantes": data_part,
        "es_autor": (conv.creador_id == request.user.id),
        "author_id": conv.creador_id,
    })

def ayuda_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            from_email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            full_subject = f"Contacto desde Gifters: {subject}"
            full_message = f"Has recibido un nuevo mensaje de:\n\nNombre: {name}\nEmail: {from_email}\n\nMensaje:\n{message}"

            try:
                send_mail(
                    subject=full_subject,
                    message=full_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=['giftersg4@gmail.com'], # Correo de destino
                    fail_silently=False,
                )
                messages.success(request, '¡Tu mensaje ha sido enviado! Te responderemos pronto.')
            except Exception:
                messages.error(request, 'Hubo un error al enviar tu mensaje. Por favor, inténtalo más tarde.')

            return redirect('ayuda')
        else:
            messages.error(request, 'Por favor, completa todos los campos del formulario.')

    return render(request, 'ayuda.html')


@login_required
@require_POST
def report_post(request, post_id):
    """Permite a un usuario reportar un post. Crea ReporteStrike y envía un email al soporte.

    Responde JSON si la petición viene como AJAX, si no redirige con messages.
    """
    post = get_object_or_404(Post, id_post=post_id)

    motivo = (request.POST.get('motivo') or request.POST.get('reason') or '').strip() or 'Contenido inapropiado'

    try:
        reporte, created = ReporteStrike.objects.get_or_create(
            id_user=request.user,
            id_post=post,
            defaults={'motivo': motivo}
        )
    except Exception as e:
        # Si algo falla al guardar, devolvemos error (no rompemos la página)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
        messages.error(request, 'No se pudo registrar el reporte. Intenta de nuevo más tarde.')
        return redirect(_next_url(request, default='/feed/'))

    if not created:
        # Ya había un reporte previo del mismo usuario
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'message': 'Ya habías reportado esta publicación.'})
        messages.info(request, 'Ya habías reportado esta publicación.')
        return redirect(_next_url(request, default='/feed/'))

    # Enviar email al soporte (usar helper)
    try:
        send_report_email(request.user, post, motivo=motivo, request=request)
    except Exception as e:
        # Log y continuar (no queremos romper la UX si falla el correo)
        try:
            log.exception('Error enviando email de reporte: %s', e)
        except Exception:
            pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'message': 'Reporte enviado. Gracias por ayudarnos a mantener la comunidad segura.'})

    messages.success(request, 'Reporte enviado. Gracias por ayudarnos a mantener la comunidad segura.')
    return redirect(_next_url(request, default='/feed/'))

# === Vistas API para Productos ===
@api_view(['POST'])
@permission_classes([IsAdminUser]) # ¡Importante! Asegura que solo los admins puedan usar esto
def upload_csv_view(request):
    """
    Recibe un archivo CSV subido desde la app de escritorio y 
    ejecuta el management command 'import_products'.
    """
    if 'csv_file' not in request.FILES:
        return Response({"error": "No se encontró el archivo 'csv_file'."}, status=status.HTTP_400_BAD_REQUEST)

    file = request.FILES['csv_file']
    file_name = ""

    try:
        # Guardar el archivo temporalmente en el sistema de archivos (en la carpeta 'media')
        file_name = default_storage.save(file.name, file)
        file_path = default_storage.path(file_name)

        # Llamar al management command que ya tienes, pasándole la ruta del archivo
        call_command('import_products', file_path)

        # Limpiar el archivo temporal
        default_storage.delete(file_name)

        # Enviar una respuesta exitosa
        return Response({"message": "Archivo CSV procesado e importación completada."}, status=status.HTTP_200_OK)

    except Exception as e:
        # Si algo sale mal, borra el archivo temporal si es que se creó
        if file_name and default_storage.exists(file_name):
            default_storage.delete(file_name)

        return Response({"error": f"Error durante la importación: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ProductoListAPIView(generics.ListCreateAPIView): # <-- CAMBIO AQUÍ
    """
    Vista de API para listar (GET) y crear (POST) productos.
    Accesible en /api/productos/
    """
    queryset = Producto.objects.filter(activo=True)
    serializer_class = ProductoSerializer
    # Mantenemos IsAuthenticated, pero podrías cambiar a IsAdminUser si solo admins pueden crear
    permission_classes = [IsAuthenticated]
    # pagination_class = ... (si usas paginación)

    # Opcional: Para asegurar que al crear se asignen bien categoría/marca por ID
    # def perform_create(self, serializer):
    #     # Aquí podrías añadir lógica extra si fuera necesario antes de guardar
    #     # por ejemplo, validar IDs de categoría/marca, pero el serializer ya lo hace.
    #     serializer.save()
class ProductoDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista de API para ver, actualizar (parcial o total) o eliminar un producto específico.
    Accesible en /api/productos/<int:pk>/
    Donde <int:pk> es el id_producto.
    """
    queryset = Producto.objects.all() # Busca en todos los productos
    serializer_class = ProductoSerializer
    permission_classes = [IsAdminUser] # Solo los administradores pueden modificar/eliminar
    lookup_field = 'pk' # Indica que el ID vendrá en la URL como 'pk'
    
# --- Vistas API para Usuarios (Admin) ---

class UserListAPIView(generics.ListAPIView):
    """
    Vista de API para listar todos los usuarios (solo para admins).
    Accesible en /api/users/
    """
    queryset = User.objects.all().order_by('id') # Obtener todos los usuarios
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser] # Solo admins pueden listar usuarios
    # Puedes añadir paginación si tienes muchos usuarios, igual que con productos

class UserDetailAPIView(generics.RetrieveUpdateDestroyAPIView): # <-- CAMBIO AQUÍ
    """
    Vista de API para ver, actualizar (parcial) o ELIMINAR un usuario específico.
    Accesible en /api/users/<int:pk>/
    Donde <int:pk> es el id del usuario.
    """
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser] # Solo admins pueden ver/editar/eliminar
    lookup_field = 'pk'
    
    def destroy(self, request, *args, **kwargs):
        """
        Anula el método de borrado para añadir una capa de seguridad.
        """
        instance = self.get_object() # Este es el usuario que se intenta borrar

        # --- REGLA DE NEGOCIO: Prohibir borrado de admins ---
        # Verificamos 'is_staff' (admin de Django) O 'es_admin' (tu campo)
        if instance.is_staff or getattr(instance, 'es_admin', False):
            logging.warning(f"El admin '{request.user}' intentó eliminar al admin '{instance}'. ¡Acción bloqueada!")
            # 403 Forbidden es el código correcto para una acción no permitida
            return Response(
                {"detail": "No se puede eliminar a un usuario administrador. "
                           "Para eliminarlo, primero quítele los permisos de administrador (is_staff y es_admin)."},
                status=status.HTTP_403_FORBIDDEN 
            )
        
        # Si la verificación pasa (no es admin), proceder con el borrado normal
        logging.info(f"El admin '{request.user}' está borrando al usuario '{instance}'.")
        return super().destroy(request, *args, **kwargs)

class CategoriaListAPIView(generics.ListCreateAPIView): 
    """
    Vista de API para listar Y CREAR todas las Categorías.
    """
    queryset = Categoria.objects.all().order_by('nombre_categoria')
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminUser]

class MarcaListAPIView(generics.ListCreateAPIView): 
    """
    Vista de API para listar Y CREAR todas las Marcas.
    """
    queryset = Marca.objects.all().order_by('nombre_marca')
    serializer_class = MarcaSerializer
    permission_classes = [IsAdminUser]
    
@api_view(['GET'])
@permission_classes([IsAdminUser]) # ¡MUY IMPORTANTE!
def get_web_app_logs(request):
    """
    Endpoint de API para que los admins vean los logs del servidor web.
    Devuelve las últimas 500 líneas del archivo 'web_app.log'.
    """
    try:
        log_file_path = settings.LOGGING_DIR / 'web_app.log'
        
        # Verificar si el archivo existe
        if not os.path.exists(log_file_path):
            return Response(
                {"error": "El archivo de log aún no ha sido creado."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Leer las últimas 500 líneas de forma eficiente
        lines = []
        with open(log_file_path, 'r', encoding='utf-8') as f:
            # Usamos deque para mantener solo las N últimas líneas en memoria
            last_lines = deque(f, 500)
            lines = list(last_lines)
            
        # Devolvemos las líneas (pueden estar vacías si el log es nuevo)
        return Response(lines, status=status.HTTP_200_OK)

    except Exception as e:
        # Loggear el error de lectura (solo se verá en la consola de Docker)
        print(f"Error al leer el archivo de log: {e}") 
        return Response(
            {"error": f"No se pudo leer el archivo de log: {e}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


 # === Listar miembros de grupo ===
@login_required
@require_http_methods(["GET"])
def grupos_members(request, pk: int):
    conv = _get_group_or_403(request, pk)
    if not conv:
        return HttpResponseForbidden("No tienes acceso a este grupo")

    part_qs = (ParticipanteConversacion.objects
               .select_related("usuario", "usuario__perfil")
               .filter(conversacion=conv)
               .order_by("usuario__nombre", "usuario__apellido"))

    data = []
    for p in part_qs:
        u = p.usuario
        # arma avatar absoluto si existe
        avatar_url = None
        try:
            pic = getattr(getattr(u, "perfil", None), "profile_picture", None)
            if pic:
                avatar_url = request.build_absolute_uri(pic.url)
        except Exception:
            pass

        data.append({
            "id": u.id,
            "username": u.nombre_usuario or "",
            "nombre": u.nombre or "",
            "apellido": u.apellido or "",
            "rol": p.rol,  # "admin" | "miembro"
            "avatar_url": avatar_url,
        })

    # quién es el creador (autor del grupo)
    return JsonResponse({
        "conversacion_id": conv.conversacion_id,
        "creador_id": conv.creador_id,
        "miembros": data,
        "soy_admin": _is_group_admin(request.user, conv),
    })
# === Agregar miembros (solo autor) ===
@login_required
@require_http_methods(["POST"])
def grupos_add_members(request, pk: int):
    conv = _get_group_or_403(request, pk)
    if not conv:
        return HttpResponseForbidden("No tienes acceso a este grupo")
    if not _is_group_admin(request.user, conv):
        return JsonResponse({'error': 'Solo el autor/admin puede agregar miembros'}, status=403)

    try:
        body = json.loads(request.body or '{}')
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    ids = body.get('miembros') or body.get('ids') or []
    if not isinstance(ids, list):
        return JsonResponse({'error': "'miembros' debe ser lista de enteros"}, status=400)

    try:
        ids = [int(x) for x in ids]
    except Exception:
        return JsonResponse({'error': 'IDs inválidos'}, status=400)

    ya = set(ParticipanteConversacion.objects
             .filter(conversacion=conv)
             .values_list("usuario_id", flat=True))
    a_crear_ids = [i for i in ids if i not in ya]

    users = list(User.objects.filter(id__in=a_crear_ids).distinct())
    if not users:
        return JsonResponse({"ok": True, "agregados": []})

    with transaction.atomic():
        ParticipanteConversacion.objects.bulk_create([
            ParticipanteConversacion(
                conversacion=conv,
                usuario=u,
                rol=ParticipanteConversacion.Rol.MIEMBRO
            ) for u in users
        ])

    agregados_ids = [u.id for u in users]

    return JsonResponse({"ok": True, "agregados": agregados_ids})
# === Quitar miembro (solo autor) ===
@login_required
@require_http_methods(["POST"])
def grupos_remove_member(request, pk: int):
    conv = _get_group_or_403(request, pk)
    if not conv:
        return HttpResponseForbidden("No tienes acceso a este grupo")
    if not _is_group_admin(request.user, conv):
        return JsonResponse({'error': 'Solo el autor/admin puede quitar miembros'}, status=403)

    try:
        body = json.loads(request.body or '{}')
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    miembro_id = body.get('miembro_id')
    if not miembro_id:
        return JsonResponse({'error': 'Falta miembro_id'}, status=400)

    # no puedes quitar al creador
    if int(miembro_id) == conv.creador_id:
        return JsonResponse({'error': 'No puedes quitar al autor del grupo'}, status=400)

    # si es admin y es el único admin, impide dejar al grupo sin admins
    part = ParticipanteConversacion.objects.filter(conversacion=conv, usuario_id=miembro_id).first()
    if not part:
        return JsonResponse({'ok': True, 'removido': miembro_id})  # ya no estaba

    if part.rol == ParticipanteConversacion.Rol.ADMIN:
        admins = ParticipanteConversacion.objects.filter(
            conversacion=conv, rol=ParticipanteConversacion.Rol.ADMIN
        ).exclude(usuario_id=miembro_id)
        if not admins.exists():
            return JsonResponse({'error': 'No puedes dejar el grupo sin administradores'}, status=400)

    part.delete()
    # Sube la conversación para reordenar bandeja
    conv.actualizada_en = timezone.now()
    conv.save(update_fields=["actualizada_en"])

    # Avisar al usuario removido (para que desaparezca la conversación)
    _push_inbox(
        [int(miembro_id)],
        {
            "kind": "group_removed",
            "conversacion_id": conv.conversacion_id,
        }
    )

    # Avisar al resto de miembros para refrescar su bandeja/miembros
    resto_ids = list(
        ParticipanteConversacion.objects
        .filter(conversacion=conv)
        .values_list("usuario_id", flat=True)
    )
    _push_inbox(
        resto_ids,
        {
            "kind": "inbox_refresh",
            "conversacion_id": conv.conversacion_id,
            "reason": "group_member_removed",
            "removed_id": int(miembro_id),
        }
    )

    return JsonResponse({'ok': True, 'removido': int(miembro_id)})
    

# === Eliminar grupo (solo autor) ===
@login_required
@require_http_methods(["POST"])
def grupos_delete(request, pk: int):
    conv = _get_group_or_403(request, pk)
    if not conv:
        return HttpResponseForbidden("No tienes acceso a este grupo")
    # Solo el autor puede eliminar el grupo
    if conv.creador_id != request.user.id:
        return JsonResponse({'error': 'Solo el autor puede eliminar el grupo'}, status=403)

    deleted_id = conv.conversacion_id
    conv.delete()
    return JsonResponse({'ok': True, 'deleted_id': deleted_id})

def _get_group_or_403(request, pk: int):
    """
    Devuelve la conversación de tipo GRUPO si el usuario es participante.
    Si no es participante, devuelve None para que la vista responda 403.
    """
    conv = get_object_or_404(
        Conversacion,
        conversacion_id=pk,
        tipo=Conversacion.Tipo.GRUPO,
    )
    # Debe pertenecer al grupo
    if not ParticipanteConversacion.objects.filter(conversacion=conv, usuario=request.user).exists():
        return None
    return conv

def _is_group_admin(user: User, conv: Conversacion) -> bool:
    """
    True si el usuario es el creador del grupo o si tiene rol ADMIN en ese grupo.
    """
    if conv.creador_id == user.id:
        return True
    return ParticipanteConversacion.objects.filter(
        conversacion=conv, usuario=user, rol=ParticipanteConversacion.Rol.ADMIN
    ).exists()

@login_required
def sugerencias_regalo_ia(request, amigo_username):
    """
    Genera sugerencias de regalo para un amigo usando OpenAI GPT.
    """
    amigo = get_object_or_404(User, nombre_usuario=amigo_username)
    perfil_amigo = getattr(amigo, 'perfil', None)

    # 1. Recolectar datos del amigo (¡Puedes mejorar esto!)
    datos_amigo = f"Nombre: {amigo.nombre} {amigo.apellido}\n"
    if perfil_amigo and perfil_amigo.bio:
        datos_amigo += f"Biografía: {perfil_amigo.bio}\n"

    try:
        # Asume una wishlist por usuario
        wl = Wishlist.objects.get(usuario=amigo)
        items = ItemEnWishlist.objects.filter(
            id_wishlist=wl,
            fecha_comprado__isnull=True # Solo items no comprados
        ).select_related('id_producto')[:5] # Limita a 5 items para no exceder tokens

        nombres_items = [item.id_producto.nombre_producto for item in items]
        if nombres_items:
            datos_amigo += f"Algunos items que quiere: {', '.join(nombres_items)}\n"
        else:
             datos_amigo += "No tiene items visibles en su wishlist.\n"
    except Wishlist.DoesNotExist:
        datos_amigo += "No tiene items visibles en su wishlist.\n"

    # Podrías añadir intereses, posts recientes, etc. si los tienes modelados

    # 2. Diseñar el Prompt para GPT
    prompt = (
        f"Eres GifterAI, un experto en encontrar el regalo perfecto.\n"
        f"Mi amigo se llama {amigo.nombre}. Aquí hay algo de información sobre él/ella:\n{datos_amigo}\n"
        f"Basado en esto, sugiere 5 ideas de regalos creativas y personalizadas. "
        f"Para cada idea, explica brevemente por qué sería un buen regalo para {amigo.nombre}. "
        f"Formato deseado:\n"
        f"- **[Idea de Regalo]:** [Explicación breve]."
    )

    sugerencias_texto = "Lo siento, no pude generar sugerencias en este momento. Intenta más tarde."
    sugerencias_lista = []

    
    if openai.api_key:
        try:
            print(f"Enviando prompt a OpenAI para {amigo_username}...") 
            # Usa la nueva forma de llamar a la API v1.x.x
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY) # Crea un cliente
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", # Modelo económico y rápido
                messages=[
                    {"role": "system", "content": "Eres GifterAI, un asistente experto en regalos."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200, # Ajusta según necesites más o menos texto
                n=1, # Solo queremos una respuesta
                stop=None, # No necesitamos parar la generación antes
                temperature=0.7, # Un poco creativo pero no demasiado loco
            )

            print("Respuesta recibida de OpenAI.") # Log para depurar
            # 4. Procesar la respuesta
            if response.choices:
                sugerencias_texto = response.choices[0].message.content.strip()
                # Intenta separar las sugerencias en una lista para el template
                sugerencias_lista = [s.strip() for s in sugerencias_texto.split('\n') if s.strip().startswith('-')]
            else:
                sugerencias_texto = "OpenAI no devolvió sugerencias."

        except openai.APIError as e:
            print(f"Error de API OpenAI: {e.status_code} - {e.response}")
            sugerencias_texto = f"Error al contactar OpenAI ({e.status_code}). Intenta más tarde."
        except Exception as e:
            print(f"Error inesperado llamando a OpenAI: {e}")
            sugerencias_texto = "Ocurrió un error inesperado al generar sugerencias."
    else:
         sugerencias_texto = "La API Key de OpenAI no está configurada en el servidor."


    # 5. Mostrar al usuario en una plantilla
    context = {
        'amigo': amigo,
        'sugerencias_raw': sugerencias_texto, # El texto completo por si falla el split
        'sugerencias_lista': sugerencias_lista # La lista para el template
    }
    # Asegúrate que la ruta a tu plantilla sea correcta
    return render(request, 'core/sugerencias_regalo_ia.html', context)


@login_required
@require_POST
def grupos_leave(request, pk: int):
    # 1) Traer el grupo por conversacion_id y tipo GRUPO
    conv = get_object_or_404(
        Conversacion,
        conversacion_id=pk,
        tipo=Conversacion.Tipo.GRUPO
    )

    # 2) El autor no puede salir (debe eliminar o transferir admin)
    if getattr(conv, "creador_id", None) == request.user.id:
        return JsonResponse(
            {"ok": False, "error": "El autor no puede abandonar el grupo."},
            status=400
        )

    # 3) Borrar la membresía del usuario en ParticipanteConversacion
    deleted, _ = ParticipanteConversacion.objects.filter(
        conversacion=conv,
        usuario=request.user
    ).delete()

    if deleted == 0:
        return JsonResponse(
            {"ok": False, "error": "No eres miembro de este grupo."},
            status=404
        )

    _push_inbox([request.user.id], {"kind": "group_left", "conversacion_id": conv.conversacion_id})

    conv.actualizada_en = timezone.now()
    conv.save(update_fields=["actualizada_en"])

    resto_ids = list(
        ParticipanteConversacion.objects
        .filter(conversacion=conv)
        .values_list("usuario_id", flat=True)
    )
    _push_inbox(resto_ids, {
        "kind": "inbox_refresh",
        "conversacion_id": conv.conversacion_id,
        "reason": "group_left",
        "left_id": request.user.id,
    })
    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["POST"])
def conversacion_mark_read(request, conv_id: int):
    from core.models import EntregaMensaje
    updated = (EntregaMensaje.objects
               .filter(
                   usuario=request.user,
                   estado=EntregaMensaje.Estado.ENTREGADO,
                   mensaje__conversacion_id=conv_id
               )
               .update(estado=EntregaMensaje.Estado.LEIDO, timestamp=timezone.now()))
    # Push local para refrescar la bandeja del mismo usuario
    from .utils import _push_inbox
    _push_inbox([request.user.id], {
        "kind": "inbox_refresh",
        "conversacion_id": conv_id,
        "reason": "mark_read"
    })
    return JsonResponse({"ok": True, "updated": updated})


@login_required
@require_http_methods(["GET"])
def chat_unread_summary(request):
    from core.models import EntregaMensaje
    qs = (EntregaMensaje.objects
          .filter(usuario=request.user, estado=EntregaMensaje.Estado.ENTREGADO)
          .values("mensaje__conversacion_id")
          .annotate(cnt=Count("entrega_id")))

    per_conv = {str(r["mensaje__conversacion_id"]): r["cnt"] for r in qs}
    total = sum(per_conv.values())
    return JsonResponse({"total": total, "per_conversation": per_conv})
#################
############
############
####################DESKTOP FUNCTIONS!!!

@api_view(['GET'])  
@permission_classes([IsAdminUser])  
def download_active_products_csv(request):  
    """
    Genera y devuelve un archivo CSV con todos los productos activos.
    """
    try:
        productos = Producto.objects.filter(activo=True).select_related('id_categoria', 'id_marca').order_by('id_producto')  
        filename_base = f"productos_activos_{datetime.date.today()}"  

        response = HttpResponse(  
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename_base}.csv"'},
        )
        response.write('\ufeff'.encode('utf8')) # BOM  
        writer = csv.writer(response, delimiter=';')  

        # Encabezado
        writer.writerow([  
            'ID Producto', 'Nombre', 'Descripcion', 'Precio',
            'Categoria ID', 'Categoria Nombre', 'Marca ID', 'Marca Nombre', 'URL Imagen'
        ])
        # Filas
        for producto in productos:  
            writer.writerow([  
                producto.id_producto, producto.nombre_producto, producto.descripcion, producto.precio,
                producto.id_categoria_id, producto.id_categoria.nombre_categoria if producto.id_categoria else '',
                producto.id_marca_id, producto.id_marca.nombre_marca if producto.id_marca else '',
                request.build_absolute_uri(producto.imagen.url) if producto.imagen else ''
            ])
        return response  

    except Exception as e:
        print(f"Error generando CSV de productos: {e}")  
        return Response({"error": f"No se pudo generar el reporte CSV: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  
    
    
@api_view(['GET'])  
@permission_classes([IsAdminUser])  
def download_active_products_pdf(request): # Nuevo nombre de función
    """
    Genera y devuelve un archivo PDF con todos los productos activos.
    """
    try:
        productos = Producto.objects.filter(activo=True).select_related('id_categoria', 'id_marca').order_by('id_producto')  
        filename_base = f"productos_activos_{datetime.date.today()}"  

        # Lógica de generación de PDF (la misma que tenías antes)
        template = get_template('reports/product_report_pdf.html')  
        context = {  
            'productos': productos,  
            'generation_date': timezone.now()  
        }
        html = template.render(context)  
        result = BytesIO()  
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)  

        if not pdf.err:  
            response = HttpResponse(result.getvalue(), content_type='application/pdf')  
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.pdf"'  
            return response  
        else:
            print(f"Error generando PDF: {pdf.err}")  
            return Response({"error": "No se pudo generar el reporte PDF."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  

    except Exception as e:
        print(f"Error generando PDF de productos: {e}") # Mensaje específico
        return Response({"error": f"No se pudo generar el reporte PDF: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  
    
@api_view(['GET'])  
@permission_classes([IsAdminUser])  
def download_active_products_excel(request): # Nuevo nombre específico
    """
    Genera y devuelve un archivo Excel (.xlsx) con todos los productos activos.
    """
    try:
        # Obtener datos (igual que en las otras vistas)
        productos = Producto.objects.filter(activo=True).select_related('id_categoria', 'id_marca').order_by('id_producto')  
        filename_base = f"productos_activos_{datetime.date.today()}"  

        # Preparar datos para Pandas (igual que antes)
        data_list = []
        for p in productos:
            data_list.append({
                'ID Producto': p.id_producto,
                'Nombre': p.nombre_producto,
                'Descripcion': p.descripcion,
                'Precio': p.precio,
                'Categoria ID': p.id_categoria_id,
                'Categoria Nombre': p.id_categoria.nombre_categoria if p.id_categoria else '',
                'Marca ID': p.id_marca_id,
                'Marca Nombre': p.id_marca.nombre_marca if p.id_marca else '',
                'URL Imagen': request.build_absolute_uri(p.imagen.url) if p.imagen else ''
            })
        df = pd.DataFrame(data_list) # Crear DataFrame

        # Configurar respuesta para Excel
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  
        )
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'  

        # Escribir DataFrame a Excel en la respuesta
        df.to_excel(response, index=False, engine='openpyxl')  
        return response  

    except Exception as e:
        print(f"Error generando Excel de productos: {e}") # Mensaje específico
        return Response({"error": f"No se pudo generar el reporte Excel: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  


#
# --- INICIO DE NUEVAS VISTAS DE REPORTES DE USUARIO (CORREGIDO) ---
#

class ModerationReportAPIView(APIView):
    """
    Reporte de Moderación:
    - Usuarios que más reportan.
    - Usuarios que más han sido reportados.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Usuarios que más reportan
        top_reporters = (
            ReporteStrike.objects
            .values('id_user__id', 'id_user__nombre_usuario')
            .annotate(count=Count('id_reporte'))
            .order_by('-count')[:20]
        )

        # Usuarios (autores de posts) que más han sido reportados
        most_reported_users = (
            ReporteStrike.objects
            .exclude(id_post__id_usuario__isnull=True) # Ignorar reportes sin post o autor
            .values('id_post__id_usuario__id', 'id_post__id_usuario__nombre_usuario')
            .annotate(count=Count('id_reporte'))
            .order_by('-count')[:20]
        )

        return Response({
            "top_reporters": list(top_reporters),
            "most_reported_users": list(most_reported_users),
        })


class PopularSearchReportAPIView(APIView):
    """
    Reporte de Búsquedas Populares:
    - Devuelve los términos más buscados en HistorialBusqueda.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        popular_terms = (
            HistorialBusqueda.objects
            .annotate(term_lower=Lower(Trim('term'))) # Normalizar
            .values('term_lower')
            .annotate(count=Count('id_search'))
            .order_by('-count')[:50] # Top 50
        )

        return Response({
            "popular_searches": list(popular_terms),
        })


class SiteReviewsReportAPIView(APIView):
    """
    Reporte de Reseñas del Sitio:
    - Conteo de estrellas (1-5).
    - Lista de las últimas 100 reseñas.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Conteo de estrellas
        review_stats = (
            ResenaSitio.objects
            .values('calificacion')
            .annotate(count=Count('id_resena'))
            .order_by('calificacion')
        )

        # Últimas reseñas (para "ver que dice cada una")
        latest_reviews = (
            ResenaSitio.objects
            .order_by('-fecha_resena')
            .select_related('id_usuario')
            .values(
                'id_usuario__nombre_usuario',
                'calificacion',
                'comentario',
                'fecha_resena'
            )[:100]
        )

        return Response({
            "review_stats": list(review_stats),
            "latest_reviews": list(latest_reviews),
        })


class TopActiveUsersReportAPIView(APIView):
    """
    Reporte de Top 10 Usuarios más Activos.
    Muestra el puntaje total y un desglose por tipo de actividad
    basado en el modelo RegistroActividad.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # 1. Obtener los IDs de los top 10 usuarios por actividad total
        top_user_ids = list(
            RegistroActividad.objects
            .values('id_usuario')
            .annotate(activity_score=Count('id_actividad'))
            .order_by('-activity_score')
            .values_list('id_usuario', flat=True)[:10] 
        )

        # 2. Obtener el desglose de actividad SOLO para esos usuarios
        activity_details = (
            RegistroActividad.objects
            .filter(id_usuario__in=top_user_ids) # Filtrar por los top 10
            .values('id_usuario__id', 'id_usuario__nombre_usuario', 'tipo_actividad') # Agrupar por usuario y tipo
            .annotate(count=Count('id_actividad'))
            .order_by('id_usuario__id', 'tipo_actividad') # Ordenar para procesar fácilmente
        )

        # 3. Procesar los resultados para agrupar por usuario
        results = {}
        for detail in activity_details:
            user_id = detail['id_usuario__id']
            username = detail['id_usuario__nombre_usuario']
            activity_type = detail['tipo_actividad']
            count = detail['count']

            if user_id not in results:
                results[user_id] = {
                    'user_id': user_id,
                    'nombre_usuario': username,
                    'total_score': 0,
                    'breakdown': { # Inicializar desglose con ceros
                        RegistroActividad.TipoActividad.NUEVO_POST: 0,
                        RegistroActividad.TipoActividad.NUEVO_COMENT: 0,
                        RegistroActividad.TipoActividad.NUEVA_REACCION: 0,
                        RegistroActividad.TipoActividad.NUEVO_SEGUIDOR: 0,
                        RegistroActividad.TipoActividad.NUEVO_REGALO: 0,
                        RegistroActividad.TipoActividad.OTRO: 0, 
                    }
                }
            
            # Sumar al total y al desglose específico
            results[user_id]['total_score'] += count
            if activity_type in results[user_id]['breakdown']:
                 results[user_id]['breakdown'][activity_type] = count

        # Convertir el diccionario a una lista ordenada por puntaje total (descendente)
        final_list = sorted(results.values(), key=lambda x: x['total_score'], reverse=True)
        
        # Calcular el total general de interacciones (como antes)
        total_interactions = RegistroActividad.objects.count()

        return Response({
            "top_active_users": final_list,
            "total_tracked_interactions": total_interactions,
        })
class UserActivityDetailAPIView(APIView):
    """
    Reporte detallado de la actividad de UN solo usuario.
    Ideal para ver el "perfil" de un usuario desde el admin.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk=None):
        if pk is None:
            return Response({"error": "Se requiere un ID de usuario."}, status=400)
        
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "Usuario no encontrado."}, status=404)

        # Consultas de actividad
        data = {
            "user_id": user.id,
            "nombre_usuario": user.nombre_usuario,
            "seguidores": Seguidor.objects.filter(seguido=user).count(),
            "siguiendo": Seguidor.objects.filter(seguidor=user).count(),
            "solicitudes_enviadas": SolicitudAmistad.objects.filter(emisor=user).count(),
            "bloqueos_realizados": BloqueoDeUsuario.objects.filter(blocker=user).count(),
            "veces_bloqueado": BloqueoDeUsuario.objects.filter(blocked=user).count(),
            "posts_creados": Post.objects.filter(id_usuario=user).count(),
            "comentarios_escritos": Comentario.objects.filter(usuario=user).count(),
            "likes_dados": Like.objects.filter(id_usuario=user).count(),
            "postales_generadas": GeneratedCard.objects.filter(user=user).count(),
            "regalos_dados": HistorialDeRegalos.objects.filter(id_user=user).count(),
        }
        
        # Lista de quién ha bloqueado a este usuario
        blocked_by_list = BloqueoDeUsuario.objects.filter(blocked=user).select_related('blocker').values_list('blocker__nombre_usuario', flat=True)
        data["blocked_by_users"] = list(blocked_by_list)

        return Response(data)

# --- FIN DE NUEVAS VISTAS DE REPORTES ---
#



#######################
#####################
###################
##########FINN REPORTS FUNCTIONS    
def producto_detalle(request, id_producto=None, pk=None):
    """
    Vista de detalle del producto.
    Acepta tanto `id_producto` como `pk` (por compatibilidad con URLs o templates).
    """
    producto_id = id_producto or pk

    # Producto + relaciones necesarias
    producto = get_object_or_404(
        Producto.objects
        .select_related("id_marca", "id_categoria")
        .prefetch_related(
            Prefetch(
                "urls_tienda",
                queryset=UrlTienda.objects.filter(activo=True).order_by("-es_principal", "-pk"),
                to_attr="urls_tienda_activas_qs",
            )
        ),
        pk=producto_id,
    )

    # URL principal de tienda (propiedad del modelo o fallback)
    url_principal = producto.url_tienda_principal or producto.url or None

    # IDs de productos en wishlist (para el corazón)
    favoritos_ids = set()
    if request.user.is_authenticated:
        try:
            wl = get_default_wishlist(request.user)
            favoritos_ids = set(
                ItemEnWishlist.objects
                .filter(id_wishlist=wl)
                .values_list("id_producto", flat=True)
            )
        except Exception:
            favoritos_ids = set()

    # Productos similares (por marca o categoría)
    similares = list(
        Producto.objects
        .filter(activo=True, id_marca=producto.id_marca)
        .exclude(pk=producto.pk)
        .select_related("id_marca", "id_categoria")
        .prefetch_related("urls_tienda")[:6]
    )

    if not similares:
        similares = list(
            Producto.objects
            .filter(activo=True, id_categoria=producto.id_categoria)
            .exclude(pk=producto.pk)
            .select_related("id_marca", "id_categoria")
            .prefetch_related("urls_tienda")[:6]
        )

    context = {
        "producto": producto,
        "url_principal": url_principal,
        "favoritos_ids": favoritos_ids,
        "similares": similares,
    }
    return render(request, "producto_detalle.html", context)

def ver_card_publica(request, slug):
    card = get_object_or_404(GeneratedCard, share_token=slug)
    img_abs_url = request.build_absolute_uri(card.image.url) if card.image else ""
    page_abs_url = request.build_absolute_uri()
    return render(request, "cards/ver_publica.html", {
        "card": card,
        "img_abs_url": img_abs_url,
        "page_abs_url": page_abs_url,
    })


HF_PRIMARY  = "stabilityai/stable-diffusion-xl-base-1.0"
HF_FALLBACK = "stabilityai/stable-diffusion-xl-base-1.0"
HF_PRIMARY  = os.getenv("HF_PRIMARY", "stabilityai/sdxl-turbo").strip()
HF_TIMEOUT = 25    
POLL_TIMEOUT = 20 

def _bad(payload: dict):
    return HttpResponseBadRequest(json.dumps(payload), content_type="application/json")

def _hf_generate(hf_token: str, model: str, prompt: str, timeout: int = 25):
    url = f"https://api-inference.huggingface.co/models/{model}"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {hf_token}", "Accept": "image/png"},
        json={"inputs": prompt, "options": {"wait_for_model": True}},
        timeout=timeout,
    )
    return url, resp

def _pollinations_url(prompt: str, w: int = 1024, h: int = 1024):
    q = quote(prompt)
    return f"https://image.pollinations.ai/prompt/{q}?width={w}&height={h}&nofeed=true"


@login_required
@require_POST
def generar_card_hf(request):
    prompt = (request.POST.get("prompt") or "").strip()
    style  = (request.POST.get("style")  or "postal minimalista con borde sutil").strip()
    if not prompt:
        return JsonResponse({"ok": False, "error": "Falta 'prompt'"}, status=400)

    full_prompt = f"{prompt}. Estilo: {style}. composición centrada, formato 1:1, fondo claro, tipografía limpia, borde sutil, alta calidad."

    hf_token = os.getenv("HF_TOKEN")
    hf_model = os.getenv("HF_MODEL", "stabilityai/sdxl-turbo")

    img_bytes = None
    provider  = None
    tried = []

    # 1) Intento Hugging Face (si hay token). Si falla, NO devolvemos 502: seguimos a fallback.
    if hf_token:
        try:
            url_hf = f"https://api-inference.huggingface.co/models/{hf_model}"
            r = requests.post(
                url_hf,
                headers={"Authorization": f"Bearer {hf_token}", "Accept": "image/png"},
                json={"inputs": full_prompt, "options": {"wait_for_model": True}},
                timeout=HF_TIMEOUT,
            )
            tried.append({"provider": "huggingface", "status": r.status_code})
            if r.status_code == 200 and r.content:
                img_bytes = r.content
                provider = "huggingface"
        except requests.RequestException as e:
            tried.append({"provider": "huggingface", "error": str(e)})

    # 2) Fallback Pollinations (solo si aún no tenemos imagen)
    if img_bytes is None:
        poll = _pollinations_url(full_prompt, 1024, 1024)
        try:
            r2 = requests.get(poll, timeout=POLL_TIMEOUT)
            tried.append({"provider": "pollinations", "status": r2.status_code})
            if r2.status_code == 200 and r2.content:
                img_bytes = r2.content
                provider = "pollinations"
            else:
                return JsonResponse(
                    {"ok": False, "error": "Ningún proveedor devolvió 200", "tried": tried},
                    status=502
                )
        except requests.RequestException as e:
            return JsonResponse(
                {"ok": False, "error": "Falló también el fallback", "detail": str(e), "tried": tried},
                status=502
            )

    # 3) Guardar y responder 200
    from core.models import GeneratedCard
    card = GeneratedCard.objects.create(user=request.user, prompt=prompt)
    card.image.save(f"card_{card.id}.png", ContentFile(img_bytes), save=True)

    return JsonResponse({
        "ok": True,
        "id": card.id,
        "url": "https://picsum.photos/800",
        "share": "https://picsum.photos/800",
        "provider": provider,
        "tried": tried
    }, status=200)



 ### apartadiño evento amigo secret
def _is_group(conv: Conversacion) -> bool:
    return bool(getattr(conv, 'is_group', False) or str(getattr(conv, 'tipo', '')).lower() == 'grupo')

def _is_member(conv: Conversacion, user) -> bool:
    # Ajusta a tu relación real de participantes
    return any(int(getattr(p, 'id', 0)) == int(user.id) for p in (conv.participantes.all() if hasattr(conv, 'participantes') else []))

def _is_author(conv: Conversacion, user) -> bool:
    # Ajusta al campo real del creador/autor del grupo.
    # Algunos modelos usan 'creador' (creador_id), otros usan 'autor' o 'author'.
    # Intentamos varias opciones de forma robusta.
    try:
        uid = int(user.id)
    except Exception:
        return False

    # Revisar variantes *_id primero (más comunes y rápidas)
    for id_attr in ('creador_id', 'autor_id', 'author_id', 'owner_id', 'creator_id'):
        val = getattr(conv, id_attr, None)
        try:
            if val is not None and int(val) == uid:
                return True
        except Exception:
            pass

    # Revisar atributos relacionados que pueden ser objetos (creador, autor, author)
    for obj_attr in ('creador', 'autor', 'author', 'owner', 'creator'):
        obj = getattr(conv, obj_attr, None)
        if obj is None:
            continue
        try:
            if getattr(obj, 'id', None) is not None and int(getattr(obj, 'id')) == uid:
                return True
        except Exception:
            continue

    return False

@login_required
@require_http_methods(["GET", "POST"])
def events_list_create(request, conversacion_id):
    conv = get_object_or_404(Conversacion, pk=conversacion_id)

    if request.method == 'GET':
        if conv.tipo == Conversacion.Tipo.GRUPO:
            qs = ConversationEvent.objects.filter(conversacion=conv).order_by('-id')
        elif conv.tipo == Conversacion.Tipo.EVENTO:
            qs = ConversationEvent.objects.filter(conversacion=conv)  # 1 elemento
        else:
            return JsonResponse({"results": []})

        results = [{
            "id": e.id,
            "titulo": e.titulo,
            "estado": e.estado,
            "presupuesto": e.presupuesto_fijo,
            "creado_en": e.creado_en,
        } for e in qs]

        return JsonResponse({"results": results})

    # POST (crear): solo tiene sentido cuando la sala es GRUPO
    if request.method == 'POST':
        if conv.tipo != Conversacion.Tipo.GRUPO:
            return JsonResponse({"error": "Solo los grupos pueden crear múltiples eventos."}, status=400)

        payload = json.loads(request.body or "{}")
        titulo = (payload.get("titulo") or "").strip() or "Amigo Secreto"
        presupuesto = payload.get("presupuesto_fijo") or None

        ce = ConversationEvent.objects.create(
            conversacion=conv,
            tipo='secret_santa',
            creado_por=request.user,
            titulo=titulo,
            presupuesto_fijo=presupuesto,
            estado='borrador'
        )
        return JsonResponse({"id": ce.id}, status=201)

    return JsonResponse({"error": "Método no permitido"}, status=405)

@login_required
@require_http_methods(["GET"])
def event_detail(request, evento_id):
    try:
        ev = ConversationEvent.objects.select_related('conversacion').get(pk=evento_id)
    except ConversationEvent.DoesNotExist:
        return HttpResponseBadRequest("Evento no existe")

    conv = ev.conversacion
    if not _is_group(conv) or not _is_member(conv, request.user):
        return HttpResponseForbidden("No permitido")

    # Admin ve todas las asignaciones; miembros ven meta
    payload = {
        "id": ev.id, "tipo": ev.tipo, "titulo": ev.titulo, "presupuesto": str(ev.presupuesto_fijo) if ev.presupuesto_fijo is not None else None,
        "estado": ev.estado, "creado_en": ev.creado_en.isoformat(),
    }
    if _is_author(conv, request.user):
        payload["asignaciones"] = [
            {"da": a.da_id, "recibe": a.recibe_id}
            for a in ev.asignaciones.select_related('da', 'recibe').all()
        ]
    return JsonResponse(payload)

def _conversation_member_ids(conv: Conversacion) -> list[int]:

    # 1) Si tienes un related_name explícito para la tabla intermedia:
    if hasattr(conv, "participantes"):
        # p.ej.: conv.participantes.filter(activo=True).values_list('usuario_id', flat=True)
        try:
            return list(conv.participantes.values_list('usuario_id', flat=True))
        except Exception:
            pass

    # 2) Si tienes un M2M directo (conv.members / conv.miembros):
    for attr in ("members", "miembros", "usuarios"):
        if hasattr(conv, attr):
            try:
                return list(getattr(conv, attr).values_list('id', flat=True))
            except Exception:
                continue

    return []


def _is_user_conversation_admin(user: User, conv: Conversacion) -> bool:
    """
    Define quién puede sortear:
    - Creador/autor de la conversación, o
    - Staff, opcionalmente, o
    - (Gestión) organizador del evento (se valida más abajo).
    """
    # Si tu modelo tiene 'autor'/'author':
    if hasattr(conv, "autor_id") and conv.autor_id == user.id:
        return True
    # Permitir staff como fallback (opcional)
    if getattr(user, "is_staff", False):
        return True
    return False



# Helper: derangement (nadie se asigna a sí mismo)
def make_secret_pairs(user_ids):
    """
    Retorna un dict {giver_id: receiver_id} asegurando que nadie se asigne a sí mismo.
    Lanza ValueError si no es posible tras varios intentos (extremadamente raro si len>=2).
    """
    givers = list(user_ids)
    receivers = list(user_ids)
    for _ in range(1000):
        random.shuffle(receivers)
        if all(g != r for g, r in zip(givers, receivers)):
            return dict(zip(givers, receivers))
    raise ValueError("No fue posible generar el sorteo (derangement). Intenta de nuevo.")



@login_required
@require_http_methods(["POST"])
def event_lock(request, evento_id):
    try:
        ev = ConversationEvent.objects.select_related('conversacion').get(pk=evento_id)
    except ConversationEvent.DoesNotExist:
        return HttpResponseBadRequest("Evento no existe")

    conv = ev.conversacion
    if not _is_group(conv) or not _is_author(conv, request.user):
        return HttpResponseForbidden("Solo autor del grupo")

    ev.estado = 'cerrado'
    ev.save(update_fields=['estado'])
    return JsonResponse({"ok": True})

@login_required
@require_http_methods(["GET"])
def event_my_assignment(request, evento_id):
    try:
        ev = ConversationEvent.objects.select_related('conversacion').get(pk=evento_id)
    except ConversationEvent.DoesNotExist:
        return HttpResponseBadRequest("Evento no existe")

    conv = ev.conversacion
    if not _is_group(conv) or not _is_member(conv, request.user):
        return HttpResponseForbidden("No permitido")

    a = ev.asignaciones.filter(da=request.user).select_related('recibe').first()
    if not a:
        return JsonResponse({"has": False})

    # Devuelve INFO mínima del destinatario
    rec = a.recibe
    return JsonResponse({
        "has": True,
        "usuario": {
            "id": rec.id,
            "nombre": getattr(rec, 'nombre', '') or getattr(rec, 'first_name', '') or '',
            "apellido": getattr(rec, 'apellido', '') or getattr(rec, 'last_name', '') or '',
            "username": getattr(rec, 'nombre_usuario', '') or getattr(rec, 'username', ''),
            "avatar_url": getattr(getattr(rec, 'perfil', None), 'profile_picture_url', None) or getattr(rec, 'avatar_url', None)
        }
    })   

@login_required
def cards_crear(request, username):
    """
    Pantalla para crear/enviar una postal dirigida a `username`.
    Solo renderiza el formulario; la generación real la hace /api/cards/generar/.
    """
    User = settings.AUTH_USER_MODEL
    # Si tu User tiene campo `nombre_usuario`, úsalo para buscar:
    from django.apps import apps
    UserModel = apps.get_model(*User.split('.'))
    destinatario = get_object_or_404(UserModel, nombre_usuario=username)

    return render(request, "cards/crear.html", {
        "destinatario": destinatario,
        "username_dest": username,
    })


@login_required
@require_http_methods(["GET", "POST"])
def events_my_list_create(request):
    """
    GET: lista de eventos donde soy creador o participante (standalone)
    POST: crea un Amigo Secreto standalone (sin grupo) con la lista de amigos elegida
    """
    if request.method == "GET":
        qs = ConversationEvent.objects.filter(
            models.Q(creado_por=request.user) |
            models.Q(participantes__usuario=request.user)
        ).distinct().order_by('-creado_en')
        return JsonResponse({"results": [
            {
                "id": e.id,
                "tipo": e.tipo,
                "titulo": e.titulo,
                "presupuesto_fijo": str(e.presupuesto_fijo) if e.presupuesto_fijo is not None else None,
                "presupuesto_min": str(e.presupuesto_min) if e.presupuesto_min is not None else None,
                "presupuesto_max": str(e.presupuesto_max) if e.presupuesto_max is not None else None,
                "estado": e.estado,
                "creado_en": e.creado_en.isoformat(),
            } for e in qs
        ]})

    # POST crear
    import json, random
    try:
        p = json.loads(request.body or "{}")
    except Exception:
        p = {}

    titulo = (p.get('titulo') or 'Amigo Secreto').strip()
    miembros = p.get('miembros') or []  # IDs de usuarios (amigos seleccionados)
    pres_fijo = p.get('presupuesto_fijo', None)
    pmin = p.get('presupuesto_min', None)
    pmax = p.get('presupuesto_max', None)

    try:
        miembros = [int(x) for x in miembros if int(x) > 0]
    except Exception:
        miembros = []

    # Incluimos al creador
    ids = sorted(set(miembros + [int(request.user.id)]))
    valid, error_msg = _validate_participants_count(len(ids), is_standalone=True)
    if not valid:
        return HttpResponseBadRequest(error_msg)

    with transaction.atomic():
        ev = ConversationEvent.objects.create(
            conversacion=None,                     # ⬅️ standalone
            tipo='secret_santa',
            creado_por=request.user,
            titulo=titulo,
            presupuesto_fijo=(Decimal(str(pres_fijo)) if pres_fijo not in (None, '') else None),
            presupuesto_min=(Decimal(str(pmin)) if pmin not in (None, '') else None),
            presupuesto_max=(Decimal(str(pmax)) if pmax not in (None, '') else None),
            estado='borrador'
        )

        # Participantes explícitos
        users = User.objects.filter(id__in=ids).order_by('id')
        id_list = [u.id for u in users]
        EventParticipant.objects.bulk_create([
            EventParticipant(evento=ev, usuario=u) for u in users
        ])

        # Sorteo (derangement simple)
        def derangement(a, max_tries=500):
            arr = a[:]
            for _ in range(max_tries):
                random.shuffle(arr)
                if all(x != y for x, y in zip(a, arr)):
                    return arr
            return a[1:] + a[:1]
        asignados = derangement(id_list)

        # Persistir asignaciones
        SecretSantaAssignment.objects.bulk_create([
            SecretSantaAssignment(evento=ev, da_id=g, recibe_id=r)
            for g, r in zip(id_list, asignados)
        ])
        ev.estado = 'sorteado'
        ev.save(update_fields=['estado'])

    return JsonResponse({"ok": True, "evento_id": ev.id})    

@login_required
@require_POST
def record_recommendation_feedback(request):
    """
    Registra el feedback 'dislike' de un usuario para un producto recomendado.
    """
    try:
        product_id = request.POST.get('product_id')
        if not product_id:
            return HttpResponseBadRequest('Falta el parámetro product_id.')

        product = get_object_or_404(Producto, pk=product_id)
        
        RecommendationFeedback.objects.update_or_create(
            user=request.user,
            product=product,
            defaults={'feedback_type': 'dislike'}
        )
        
        # --- 👇 2. LLAMA A LA FUNCIÓN PARA ROMPER LA CACHÉ 👇 ---
        # Justo después de guardar el feedback, invalidamos la caché de recomendaciones.
        invalidate_user_reco_cache(request.user)
        # --------------------------------------------------------
        
        return JsonResponse({'status': 'ok', 'message': 'Feedback registrado.'})

    except Producto.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Producto no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
@login_required
@require_POST
def recommendation_feedback(request):
    """
    Vista para manejar feedback de recomendaciones (me gusta/no me gusta)
    """
    try:
        product_id = request.POST.get('product_id')
        feedback_type = request.POST.get('feedback_type', 'dislike')  # 'like' o 'dislike'
        
        if not product_id:
            return JsonResponse({'status': 'error', 'message': 'Falta product_id'}, status=400)
            
        product = get_object_or_404(Producto, pk=product_id)
        
        # Registrar o actualizar el feedback
        RecommendationFeedback.objects.update_or_create(
            user=request.user,
            product=product,
            defaults={'feedback_type': feedback_type}
        )

        # Invalidamos la caché del recomendador para que no vuelva a sugerir
        # este producto inmediatamente. También intentamos devolver una nueva
        # recomendación para que el frontend la reemplace en la UI.
        try:
            from .services.recommendations import invalidate_user_reco_cache, recommend_products_for_user
            invalidate_user_reco_cache(request.user)
            new_recs = recommend_products_for_user(request.user, limit=1, exclude_ids=[int(product_id)])
            new_rec = None
            if new_recs:
                p = new_recs[0]
                imagen = None
                try:
                    imagen = p.imagen.url if p.imagen else None
                except Exception:
                    imagen = None
                new_rec = {
                    'id': getattr(p, 'id_producto', p.pk),
                    'nombre': getattr(p, 'nombre_producto', str(p)),
                    'precio': getattr(p, 'precio', None),
                    'imagen_url': imagen,
                    'url': getattr(p, 'url_tienda_principal', None) or getattr(p, 'url', None),
                }
        except Exception:
            new_rec = None

        return JsonResponse({'status': 'ok', 'message': f'Feedback {feedback_type} registrado', 'new_recommendation': new_rec})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




@require_POST
@login_required
def notificaciones_mark_all(request):
    """Marca todas las notificaciones del usuario como leídas."""
    Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    return JsonResponse({"ok": True})



def _build_notifications(user):
    """
    Devuelve una lista de dicts con 'id' (UUID en str) para las notificaciones
    visibles del usuario. SOLO LECTURA. No modifica modelos.
    """
    qs = (Notificacion.objects
          .filter(usuario=user)
          .order_by('-creada_en')
          .values_list('id', flat=True)[:10])
    # Normalizamos a dicts como espera _unread_count_for
    return [{'id': str(nid)} for nid in qs]

# Helper para contar no leídas usando tu mismo builder
def _unread_count_for(user, seen_ids: set):
    # Asegura que el conjunto sea de strings
    seen_str = {str(x) for x in (seen_ids or set())}

    # Usa tu builder real (normalmente _build_notifications)
    items = _build_notifications(user)

    return sum(1 for i in items if str(i['id']) not in seen_str)


@require_POST
@login_required
def notificacion_mark_one(request, notificacion_id):
    """
    Marca UNA notificación del usuario como leída (lookup por PK)
    y devuelve el contador actualizado.
    """
    n = get_object_or_404(Notificacion, pk=notificacion_id, usuario=request.user)
    if not n.leida:
        n.leida = True
        n.save(update_fields=["leida"])

    unread = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    return JsonResponse({"ok": True, "unread_count": unread})


@login_required
def notificacion_click(request, notificacion_id):
    """
    Marca la notificación como leída y redirige a 'home' (o a url_target si existe).
    """
    n = get_object_or_404(Notificacion, pk=notificacion_id, usuario=request.user)
    if not n.leida:
        n.leida = True
        n.save(update_fields=["leida"])

    # Prioriza url_target si la tienes en el modelo; si no, ve a 'home'
    destino = getattr(n, "url_target", None) or resolve_url("home")
    return redirect(destino)


#############################################
#######################################


@login_required
@require_POST
@transaction.atomic
def event_create_with_chat(request):
    """
    Crea:
      1) Conversación tipo EVENTO (nombre = título, creador = request.user)
      2) ParticipanteConversacion para cada usuario (incluye al creador)
      3) ConversationEvent (tipo='secret_santa', presupuesto opcional)
      4) EventParticipant por cada usuario seleccionado
    Recibe JSON: { "titulo": str, "presupuesto_fijo": number|null, "miembros": [user_id, ...] }
    """
    try:
        try:
            payload = json.loads(request.body or "{}")
        except Exception:
            return HttpResponseBadRequest("JSON inválido")

        titulo = (payload.get("titulo") or "").strip() or "Amigo Secreto"
        presupuesto_raw = payload.get("presupuesto_fijo", None)
        miembros_ids = payload.get("miembros") or []

       
        # Comprueba si el usuario ya tiene un evento con el mismo título
        evento_existente = ConversationEvent.objects.filter(
            creado_por=request.user,
            titulo=titulo
        ).exists()
    
        if evento_existente:
            # Devuelve 409 Conflict para indicar que es un duplicado
            return JsonResponse({
                "ok": False, 
                "error": "Ya tienes un evento registrado con ese mismo nombre."
            }, status=409)


        # normaliza participantes (incluye siempre al creador)
        try:
            miembros_ids = [int(x) for x in miembros_ids if int(x) > 0]
        except Exception:
            miembros_ids = []
        if request.user.id not in miembros_ids:
            miembros_ids.append(request.user.id)
        if len(miembros_ids) < 2:
            return JsonResponse({"ok": False, "error": "Debes elegir al menos 1 amigo."}, status=400)

        # presupuesto (opcional, decimal positivo)
        presupuesto = None
        if presupuesto_raw not in (None, ""):
            try:
                presupuesto = float(str(presupuesto_raw).replace(",", "."))
                if presupuesto < 0:
                    return JsonResponse({"ok": False, "error": "El monto no puede ser negativo."}, status=400)
            except Exception:
                return JsonResponse({"ok": False, "error": "Monto inválido."}, status=400)

        User = get_user_model()
        users = list(User.objects.filter(id__in=miembros_ids))

        # 1) Conversación de EVENTO
        conv = Conversacion.objects.create(
            tipo=Conversacion.Tipo.EVENTO,
            nombre=titulo,
            creador=request.user,
        )

        # 2) Participantes de conversación (through)
        pcs = []
        for u in users:
            pc, _ = ParticipanteConversacion.objects.get_or_create(
                conversacion=conv,
                usuario=u,
                defaults={"rol": ParticipanteConversacion.Rol.MIEMBRO}
            )
            pcs.append(pc)

        # 3) ConversationEvent (tu modelo de evento real)
        ce = ConversationEvent.objects.create(
            conversacion=conv,
            tipo='secret_santa',
            creado_por=request.user,
            titulo=titulo,
            presupuesto_fijo=presupuesto if presupuesto is not None else None,
            estado='borrador'
        )

        # 4) EventParticipant (participantes del evento; aquí van **User**)
        for u in users:
            EventParticipant.objects.get_or_create(
                evento=ce,
                usuario=u,
                defaults={"estado": "inscrito"}
            )

        # (opcional) Mensaje de sistema en el chat del evento
        try:
            Mensaje.objects.create(
                conversacion=conv,
                remitente=request.user,
                tipo=Mensaje.Tipo.SISTEMA,
                contenido=f"🎉 Se creó el evento “{titulo}”."
            )
        except Exception:
            pass

        return JsonResponse({
            "ok": True,
            "conversation_event_id": ce.id,
            "conversacion_id": conv.conversacion_id,
            "participantes": [u.id for u in users]
        }, status=201)

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

@login_required
def search_friends_for_thanks(request):
    """
    Busca amigos por nombre o nombre de usuario para el modal de agradecimiento.
    Esta versión NO USA 'amigos_qs' para evitar el error del modelo.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    # --- LÓGICA MANUAL PARA ENCONTRAR AMIGOS ---
    # 1. Obtiene los IDs de los usuarios que yo sigo
    ids_yo_sigo = set(Seguidor.objects.filter(seguidor=request.user).values_list('seguido_id', flat=True))
    # 2. Obtiene los IDs de los usuarios que me siguen
    ids_me_siguen = set(Seguidor.objects.filter(seguido=request.user).values_list('seguidor_id', flat=True))
    # 3. La intersección son mis amigos
    amigos_ids = ids_yo_sigo.intersection(ids_me_siguen)
    
    # 4. Busca sobre esa lista de amigos
    amigos = User.objects.filter(
        id__in=amigos_ids,
        is_active=True
    ).filter(
        Q(nombre__icontains=query) |
        Q(apellido__icontains=query) |
        Q(nombre_usuario__icontains=query)
    ).select_related('perfil')[:10]
    # --- FIN DE LA LÓGICA MANUAL ---

    results = []
    for amigo in amigos:
        avatar_url = static('img/Gifters/favicongift.png')
        if hasattr(amigo, 'perfil') and amigo.perfil and amigo.perfil.profile_picture:
            avatar_url = amigo.perfil.profile_picture.url
        
        results.append({
            'id': amigo.id,
            'text': f"{amigo.nombre} {amigo.apellido} (@{amigo.nombre_usuario})",
            'avatar': avatar_url,
        })
    return JsonResponse(results, safe=False)


@login_required
@require_POST
def create_thank_you_post(request):
    """
    Crea una publicación (Post) de agradecimiento en el feed del usuario.
    Soporta:
      - image_option = 'product' -> utiliza la imagen guardada del producto si existe
      - image_option = 'upload'  -> usa `request.FILES['image']` si viene
      - por defecto solo texto
    """
    try:
        product_id = request.POST.get('product_id')
        thanked_user_id = request.POST.get('thanked_user_id')
        image_option = request.POST.get('image_option')  # 'product' | 'upload' | None

        producto = get_object_or_404(Producto, pk=product_id) if product_id else None
        thanked_user = get_object_or_404(User, pk=thanked_user_id) if thanked_user_id else None

        contenido = (
            f"¡Muchas gracias a @{thanked_user.nombre_usuario} por este increíble regalo! 🎁\n\n"
            f"Recibí un {producto.nombre_producto}."
        ) if producto and thanked_user else (request.POST.get('contenido') or '')

        post = Post.objects.create(
            id_usuario=request.user,
            contenido=contenido,
            tipo_post=Post.TipoPost.TEXTO,
            es_publico=True
        )

        # Adjuntar imagen según la opción
        try:
            if image_option == 'product' and producto and getattr(producto, 'imagen', None):
                # Copiar binario desde storage al Post.imagen
                try:
                    # Producto.imagen puede estar en storage; leemos con storage.open
                    with producto.imagen.open(mode='rb') as f:
                        data = f.read()
                    fname = os.path.basename(producto.imagen.name or f"prod_{producto.id_producto}.jpg")
                    post.imagen.save(f"thank_{uuid.uuid4().hex}_{fname}", ContentFile(data), save=False)
                except Exception:
                    pass
            elif image_option == 'upload' and request.FILES.get('image'):
                post.imagen = request.FILES.get('image')
        except Exception:
            pass

        # Recalcular tipo si tiene imagen
        if getattr(post, 'imagen', None):
            post.tipo_post = Post.TipoPost.IMAGEN

        post.save()

        # Registro de actividad
        try:
            RegistroActividad.objects.create(
                id_usuario=request.user,
                tipo_actividad=RegistroActividad.TipoActividad.NUEVO_POST,
                id_elemento=post.id_post,
                tabla_elemento='post',
                contenido_resumen=f"Creó el post de agradecimiento: {post.contenido[:50]}..." if post.contenido else "Publicación de agradecimiento con imagen."
            )
        except Exception:
            pass

        return JsonResponse({'status': 'ok', 'message': 'Publicación de agradecimiento creada.', 'post_id': post.id_post})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def send_thank_you_notification(request):
    """
    Envía una notificación privada de agradecimiento y opcionalmente un mensaje privado en chat.
    Parámetros POST:
      - product_id
      - thanked_user_id
      - message (opcional)
      - send_private = '1' para además enviar mensaje 1:1
      - image_option = 'product' | 'upload' (opcional)
      - image file: 'image' si image_option == 'upload'
    """
    try:
        product_id = request.POST.get('product_id')
        thanked_user_id = request.POST.get('thanked_user_id')
        message = request.POST.get('message', '').strip()
        send_private = request.POST.get('send_private') in ('1', 'true', 'True')
        image_option = request.POST.get('image_option')

        producto = get_object_or_404(Producto, pk=product_id) if product_id else None
        thanked_user = get_object_or_404(User, pk=thanked_user_id)

        titulo = f"🎁 ¡{request.user.nombre} te ha enviado un agradecimiento!"
        if not message:
            mensaje_notif = f"Te agradece por el regalo: {producto.nombre_producto if producto else 'un regalo'}."
        else:
            mensaje_notif = message

        notif = Notificacion.objects.create(
            usuario=thanked_user,
            tipo=Notificacion.Tipo.SISTEMA,
            titulo=titulo,
            mensaje=mensaje_notif,
            payload={'sender_id': request.user.id, 'product_id': getattr(producto, 'id_producto', None)}
        )

        # Si piden mensaje privado: crear/usar conversación 1:1 y crear Mensaje
        sent_private = False
        if send_private:
            try:
                conv = _get_or_create_direct(request.user, thanked_user)
                # construir contenido del chat
                chat_content = mensaje_notif
                meta = {}
                # adjuntar imagen al mensaje como metadatos cuando corresponda
                if image_option == 'product' and producto and getattr(producto, 'imagen', None):
                    try:
                        img_url = request.build_absolute_uri(producto.imagen.url)
                        meta['image_url'] = img_url
                    except Exception:
                        pass
                elif image_option == 'upload' and request.FILES.get('image'):
                    up = request.FILES.get('image')
                    # guardar archivo en storage y pasar URL en metadatos
                    name = f"chat/{uuid.uuid4().hex}{os.path.splitext(up.name)[1].lower() or '.jpg'}"
                    path = default_storage.save(name, up)
                    meta['image_url'] = default_storage.url(path)

                Mensaje.objects.create(
                    conversacion=conv,
                    remitente=request.user,
                    tipo=Mensaje.Tipo.TEXTO,
                    contenido=chat_content,
                    metadatos=meta or None
                )
                sent_private = True
            except Exception:
                sent_private = False

        return JsonResponse({'status': 'ok', 'message': 'Notificación enviada.', 'sent_private': sent_private})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    
    
def _tipo_privado_value():
    """
    Devuelve el valor correcto para 'privado' según tu modelo:
    - Enum: Conversacion.Tipo.PRIVADO
    - CharField: 'privado' o 'P'
    """
    try:
        return Conversacion.Tipo.PRIVADO
    except Exception:
        # Ajusta si en tu BD usas 'P'
        return 'privado'
    
@login_required
@require_POST
@transaction.atomic
def procesar_agradecimiento_desde_regalo(request):
    """
    Esta es la vista "inteligente". Recibe el ID del historial del regalo,
    descubre quién lo hizo y llama a las funciones existentes para crear el post o la notificación.
    """
    try:
        historial_id = request.POST.get('historial_regalo_id')
        tipo = request.POST.get('tipo') # 'publico' o 'privado'

        if not historial_id or not tipo:
            return JsonResponse({'status': 'error', 'message': 'Faltan datos.'}, status=400)

        # 1. Encontrar el regalo y quién lo hizo
        regalo = get_object_or_404(HistorialDeRegalos.objects.select_related('id_user', 'id_item__id_producto'), pk=historial_id)
        
        thanked_user = regalo.id_user # <-- ¡Aquí está la magia! Ya sabemos a quién agradecer.
        producto = regalo.id_item.id_producto
        
        # 2. Reutilizamos tus vistas existentes pasándoles los datos que necesitan
        if tipo == 'publico':
            # Simula una request para tu vista create_thank_you_post
            request.POST = request.POST.copy() # Hacemos una copia para poder modificarla
            request.POST['product_id'] = producto.id_producto
            request.POST['thanked_user_id'] = thanked_user.id
            return create_thank_you_post(request)

        elif tipo == 'privado':
            # Simula una request para tu vista send_thank_you_notification
            request.POST = request.POST.copy()
            request.POST['product_id'] = producto.id_producto
            request.POST['thanked_user_id'] = thanked_user.id
            # El mensaje y la foto los manejaremos en el JS
            return send_thank_you_notification(request)

        return JsonResponse({'status': 'error', 'message': 'Tipo de agradecimiento no válido.'}, status=400)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def _get_or_create_direct(u1, u2):
    """
    Conversación directa 1:1 entre u1 y u2 (en cualquier orden).
    Soporta enum o string para el tipo.
    """
    tipo_priv = _tipo_privado_value()
    qs = Conversacion.objects.filter(participantes__usuario=u1, tipo=tipo_priv)\
                             .filter(participantes__usuario=u2).distinct()
    direct = qs.first()
    if direct:
        return direct

    direct = Conversacion.objects.create(
        tipo=tipo_priv,
        nombre=''  # los DM no necesitan nombre visible
    )
    ParticipanteConversacion.objects.get_or_create(conversacion=direct, usuario=u1)
    ParticipanteConversacion.objects.get_or_create(conversacion=direct, usuario=u2)
    return direct





@login_required
@require_POST
def api_event_draw(request, event_id: int):
    # Log para debugging
    log.info(f"api_event_draw llamado con event_id={event_id}, tipo={type(event_id)}")
    print(f"DEBUG api_event_draw: recibido event_id={event_id}, tipo={type(event_id)}")
    
    # Normalizamos/validamos el ID
    try:
        event_id = int(event_id)
    except (TypeError, ValueError) as e:
        log.error(f"api_event_draw: error al convertir event_id={event_id!r} a int: {e}")
        return JsonResponse({"ok": False, "error": "ID de evento inválido", "debug": {"received": str(event_id), "error": str(e)}}, status=400)

    if event_id <= 0:
        return JsonResponse({"ok": False, "error": "ID de evento inválido", "debug": {"received": event_id}}, status=400)

    try:
        # Toda la operación de sorteo en una transacción para evitar race conditions
        with transaction.atomic():
            try:
                print(f"DEBUG: Intentando obtener evento {event_id}")
                ev = ConversationEvent.objects.select_for_update().get(pk=event_id)
                print(f"DEBUG: Evento encontrado: {ev}")
            except ConversationEvent.DoesNotExist:
                log.warning("api_event_draw: event %s not found", event_id)
                return JsonResponse({"ok": False, "error": "Evento no encontrado", "debug": {"id": event_id}}, status=404)
            except Exception as e:
                log.error(f"api_event_draw: error al obtener evento {event_id}: {str(e)}")
                return JsonResponse({"ok": False, "error": "Error al obtener el evento", "debug": {"error": str(e)}}, status=500)

            # permiso: solo el creador puede sortear
            if getattr(ev, 'creado_por_id', None) != request.user.id:
                log.warning("api_event_draw: user %s not creator of event %s", request.user.id, event_id)
                return JsonResponse({"ok": False, "error": "No tienes permiso para sortear este evento", "debug": {"creator": getattr(ev, 'creado_por_id', None)}}, status=403)

            # evitar re-sorteos
            if getattr(ev, 'estado', '') == 'sorteado' or getattr(ev, 'ejecutado_en', None):
                return JsonResponse({"ok": False, "error": "Este evento ya fue sorteado", "debug": {"estado": getattr(ev, 'estado', None)}}, status=400)

            # obtener participantes desde el modelo EventParticipant
            try:
                # Obtener participantes registrados para el evento
                participantes = list(EventParticipant.objects.filter(
                    evento=ev,
                    estado='inscrito'  # Solo participantes activos
                ).select_related('usuario'))
                users = [p.usuario for p in participantes]
                
                print(f"DEBUG: Encontrados {len(users)} participantes")
                
            except Exception as e:
                log.error(f"Error al obtener participantes: {e}")
                return JsonResponse({"ok": False, "error": "Error al obtener participantes", "debug": {"error": str(e)}}, status=500)

            # Asegurar que el creador forma parte del sorteo
            creator = ev.creado_por  # Usamos el campo directo que sabemos que existe

            # Asegurar que el creador esté en la lista
            if creator and all(u.id != creator.id for u in users):
                print(f"DEBUG: Agregando creador {creator.id} a la lista")
                # Añadir el creador a los participantes
                try:
                    EventParticipant.objects.get_or_create(
                        evento=ev, 
                        usuario=creator,
                        defaults={'estado': 'inscrito'}
                    )
                    users.append(creator)
                except Exception as e:
                    log.error(f"Error al agregar creador como participante: {e}")
                    # Continuamos de todas formas, no es crítico

            # Validar mínimo de participantes para que el sorteo sea interesante
            count = len(users)
            valid, error_msg = _validate_participants_count(count)
            if not valid:
                return JsonResponse({"ok": False, "error": error_msg, "debug": {"count": count}}, status=400)

            # Eliminar duplicados por ID (por si acaso hay participantes repetidos en la tabla)
            seen_ids = set()
            unique_users = []
            for u in users:
                uid = getattr(u, 'id', None)
                if uid is None:
                    continue
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                unique_users.append(u)
            users = unique_users

            if len(users) < 2:
                return JsonResponse({"ok": False, "error": "Se necesitan al menos 2 participantes después de deduplicar", "debug": {"count": len(users)}}, status=400)

            # generar derangement (ningún usuario se asigna a sí mismo y todos los receptores son únicos)
            asignados = _derangement(users)
            if not asignados:
                log.error("api_event_draw: derangement failed for event %s (n=%s)", event_id, len(users))
                return JsonResponse({"ok": False, "error": "No se pudo generar el sorteo", "debug": {"count": len(users)}}, status=500)

            # persistir asignaciones
            SecretSantaAssignment.objects.filter(evento=ev).delete()
            rows = [SecretSantaAssignment(evento=ev, da=g, recibe=r) for g, r in zip(users, asignados)]
            SecretSantaAssignment.objects.bulk_create(rows)

            # Notificar por privado a cada participante
            created = 0
            for giver, receiver in zip(users, asignados):
                try:
                    print(f"DEBUG: Notificando a giver={giver.id} sobre receiver={receiver.id}")
                    
                    # Verificación de seguridad contra auto-asignación
                    if giver.id == receiver.id:
                        log.error(f"api_event_draw: auto-asignación detectada para usuario {giver.id}")
                        continue

                    # Crear conversación privada entre sistema y giver
                    conv = obtener_o_crear_conv_directa(request.user, giver)
                    if not conv:
                        # Fallback: crear conversación directo
                        conv = Conversacion.objects.create(tipo='privado', nombre='')
                        ParticipanteConversacion.objects.get_or_create(conversacion=conv, usuario=request.user)
                        ParticipanteConversacion.objects.get_or_create(conversacion=conv, usuario=giver)

                    # Crear mensaje para el receptor actual del giver (no del creador)
                    mensaje = f"""🎁 *Amigo Secreto - Asignación*

¡Hola {getattr(giver, 'nombre', getattr(giver, 'first_name', ''))}! 

En el evento "{getattr(ev, 'titulo', '')}", te ha tocado regalar a:

👤 {getattr(receiver, 'nombre', getattr(receiver, 'first_name', str(receiver)))} {getattr(receiver, 'apellido', getattr(receiver, 'last_name', ''))}

{"💰 Presupuesto: $" + str(ev.presupuesto_fijo) if getattr(ev, 'presupuesto_fijo', None) else ""}

💝 Recuerda mantener el secreto hasta el día del intercambio.
📝 Puedes revisar los detalles del evento en el chat grupal."""
                    # Importante: enviar como sistema para evitar confusión sobre quién envía el mensaje
                    Mensaje.objects.create(
                        conversacion=conv_priv,
                        remitente=None,  # Mensaje de sistema
                        tipo='sistema',   # Tipo sistema para claridad
                        contenido=mensaje
                    )
                    created += 1
                except Exception as e:
                    log.exception("api_event_draw: failed to notify %s for event %s: %s", giver.id if hasattr(giver, 'id') else str(giver), event_id, e)
                    continue

            # mensaje al grupo
            try:
                Mensaje.objects.create(conversacion=ev.conversacion, remitente=request.user, tipo='texto', contenido="🎉 ¡El sorteo se ha realizado con éxito! 🎯\n\nCada participante ha recibido un mensaje privado con su asignación. Por favor, revisen sus mensajes privados para ver a quién deben regalar. 🤫\n\n¡Que empiece la diversión del Amigo Secreto! 🎁")
            except Exception:
                log.exception("api_event_draw: failed to post group message for event %s", event_id)

            # marcar evento como sorteado
            ev.estado = 'sorteado'
            if hasattr(ev, 'ejecutado_en'):
                ev.ejecutado_en = timezone.now()
            ev.save()

            return JsonResponse({"ok": True, "count": len(users), "notified": created})

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.error("api_event_draw: unexpected error for event %s: %s", event_id, e)
        log.error(tb)
        return JsonResponse({"ok": False, "error": "Error al realizar el sorteo", "debug": {"error_type": e.__class__.__name__, "error_details": str(e), "trace": tb.split('\n')[-6:]}}, status=500)

        with transaction.atomic():
            step = 'participants-qry'
        # Detecta el nombre del FK hacia el evento en EventParticipant
        fk_event_field = 'evento' if _field_exists(EventParticipant, 'evento') else (
                         'event'  if _field_exists(EventParticipant, 'event')  else None)
        fk_user_field  = 'usuario' if _field_exists(EventParticipant, 'usuario') else (
                         'user'    if _field_exists(EventParticipant, 'user')    else None)
        if not fk_event_field or not fk_user_field:
            return JsonResponse({"ok": False, "step": step, "msg": "Campos FK en EventParticipant no coinciden"}, status=500)

        user_ids = list(
            EventParticipant.objects.filter(**{fk_event_field: ev}).values_list(fk_user_field + '_id', flat=True)
        )
        user_ids = sorted({int(x) for x in user_ids if x})
        if len(user_ids) < 2:
            return JsonResponse({"ok": False, "step": step, "msg": "Se requieren al menos 2 participantes"}, status=400)

        step = 'load-users'
        User = get_user_model()
        users = list(User.objects.filter(id__in=user_ids).order_by('id'))
        if len(users) < 2:
            return JsonResponse({"ok": False, "step": step, "msg": "No se pudieron cargar usuarios"}, status=400)

        step = 'derangement'
        asignados = _derangement(users)
        if not asignados:
            return JsonResponse({"ok": False, "step": step, "msg": "No fue posible generar el sorteo"}, status=500)

        step = 'persist-assignments'
        # Detecta nombres de campos en SecretSantaAssignment
        fk_ev_field = 'evento' if _field_exists(SecretSantaAssignment, 'evento') else (
                      'event'  if _field_exists(SecretSantaAssignment, 'event')  else None)
        giver_field = 'giver' if _field_exists(SecretSantaAssignment, 'giver') else (
                      'emisor' if _field_exists(SecretSantaAssignment, 'emisor') else (
                      'da'     if _field_exists(SecretSantaAssignment, 'da')     else None))
        recv_field  = 'receiver' if _field_exists(SecretSantaAssignment, 'receiver') else (
                      'receptor' if _field_exists(SecretSantaAssignment, 'receptor') else (
                      'recibe'   if _field_exists(SecretSantaAssignment, 'recibe')   else None))
        if not fk_ev_field or not giver_field or not recv_field:
            return JsonResponse({"ok": False, "step": step, "msg": "Campos en SecretSantaAssignment no coinciden"}, status=500)

        # Borra asignaciones previas
        SecretSantaAssignment.objects.filter(**{fk_ev_field: ev}).delete()

        rows = []
        for giver, receiver in zip(users, asignados):
            rows.append(SecretSantaAssignment(**{
                fk_ev_field: ev,
                f"{giver_field}_id": giver.id,
                f"{recv_field}_id": receiver.id
            }))
        SecretSantaAssignment.objects.bulk_create(rows)

        step = 'send-private-messages'
        # Enviar mensaje privado a cada participante
        for giver in users:
            receiver = asignados[users.index(giver)]
            
            try:
                # Intentar encontrar una conversación privada existente primero
                conv_privada = Conversacion.objects.filter(
                    participantes__usuario__in=[giver, request.user],
                    tipo=_tipo_privado_value()
                ).annotate(
                    num_participantes=models.Count('participantes')
                ).filter(
                    num_participantes=2
                ).first()
                
                if not conv_privada:
                    # Crear nueva conversación privada si no existe
                    conv_privada = Conversacion.objects.create(
                        tipo=_tipo_privado_value(),
                        nombre=''  # los mensajes privados no necesitan nombre
                    )
                    
                    # Crear participantes de la conversación
                    ParticipanteConversacion.objects.bulk_create([
                        ParticipanteConversacion(conversacion=conv_privada, usuario=giver),
                        ParticipanteConversacion(conversacion=conv_privada, usuario=request.user)
                    ])
                
                # Crear mensaje privado
                mensaje_privado = f"""🎁 *Sorteo Amigo Secreto*
¡Te ha tocado regalar a *{receiver.nombre} {receiver.apellido}*!
Evento: {ev.titulo}
{f'Presupuesto: ${ev.presupuesto_fijo}' if ev.presupuesto_fijo else ''}

¡Recuerda mantener el secreto! 🤫"""
                
                Mensaje.objects.create(
                    conversacion=conv_privada,
                    remitente=request.user,
                    tipo='texto',
                    contenido=mensaje_privado
                )
            except Exception as e:
                print(f"Error al enviar mensaje a {giver.nombre}: {str(e)}")
                continue  # Continuar con el siguiente usuario aunque falle uno

        # Enviar mensaje al grupo del evento
        Mensaje.objects.create(
            conversacion=ev.conversacion,
            remitente=request.user,
            tipo='texto',
            contenido="🎉 ¡El sorteo se ha realizado! Cada participante ha recibido su asignación por mensaje privado. ¡Que empiece el Amigo Secreto! 🎁"
        )

        step = 'mark-event'
        if hasattr(ev, 'estado'):
            ev.estado = 'sorteado'
        if hasattr(ev, 'sorteado_at'):
            ev.sorteado_at = timezone.now()
        ev.save()

        return JsonResponse({"ok": True, "count": len(users)}, status=200)

    except Http404:
        return JsonResponse({"ok": False, "step": 'load-event', "msg": "Evento no existe"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "step": step, "msg": f"{e.__class__.__name__}: {e}",
                             "trace": traceback.format_exc()}, status=500)


@login_required
@require_POST
@transaction.atomic
def api_event_sortear(request, event_id: int):
    evento = get_object_or_404(Evento, pk=event_id)
    conv = evento.conversacion

    # Obtén users del evento/conv (ajusta si tu relación es distinta)
    participantes = list(
        User.objects.filter(
            id__in=ParticipanteConversacion.objects
                    .filter(conversacion=conv)
                    .values_list('usuario_id', flat=True)
        )
    )

    # Valida mínimo 3 personas (para evitar auto-asignaciones imposibles)
    if len(participantes) < 3:
        return JsonResponse({"ok": False, "msg": "Se requieren al menos 3 participantes."}, status=400)

    # Genera una permutación SIN puntos fijos (derangement)
    asignados = participantes[:]
    intentos = 0
    while True:
        random.shuffle(asignados)
        intentos += 1
        if all(p.id != a.id for p, a in zip(participantes, asignados)):
            break
        if intentos > 1000:
            return JsonResponse({"ok": False, "msg": "No fue posible completar el sorteo. Intente nuevamente."}, status=500)

    # Envía mensaje privado a cada uno indicando a quién le tocó
    # (usa tu helper de “chat privado” si lo tienes; aquí muestro uno simple)
    def get_or_create_dm(u1, u2):
        # ordena por id para no duplicar
        a, b = (u1, u2) if u1.id < u2.id else (u2, u1)
        dm = Conversacion.objects.filter(tipo='P', usuarios=a).filter(usuarios=b).first()
        if not dm:
            dm = Conversacion.objects.create(tipo='P', nombre=f"DM {a.username} - {b.username}")
            ParticipanteConversacion.objects.bulk_create([
                ParticipanteConversacion(conversacion=dm, usuario=a),
                ParticipanteConversacion(conversacion=dm, usuario=b),
            ])
        return dm

    # Puedes usar tu “usuario sistema” si existe
    sistema = User.objects.filter(username='Tia Turbina').first() or request.user

    for origen, destino in zip(participantes, asignados):
        dm = get_or_create_dm(origen, destino)
        Mensaje.objects.create(
            conversacion=dm,
            autor=sistema,
            contenido=f"🎁 Te tocó {destino.get_full_name() or '@' + destino.username} en el evento «{conv.nombre}»."
        )

    # Mensaje informativo al chat del evento (opcional)
    Mensaje.objects.create(
        conversacion=conv,
        autor=sistema,
        contenido="🔒 Se realizó el sorteo. Cada participante recibió su asignación por mensaje privado."
    )

    return JsonResponse({"ok": True})  

class CategoriaDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista de API para Ver, Actualizar o Borrar una Categoría específica.
    """
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Regla de negocio: No permitir borrar la categoría por defecto
        if instance.nombre_categoria == "Sin Categoría":
            return Response(
                {"detail": "No se puede eliminar la categoría 'Sin Categoría'."},
                status=status.HTTP_403_FORBIDDEN
            )
        logging.info(f"Admin '{request.user}' borrando Categoría: {instance.nombre_categoria}")
        return super().destroy(request, *args, **kwargs)

class MarcaDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista de API para Ver, Actualizar o Borrar una Marca específica.
    """
    queryset = Marca.objects.all()
    serializer_class = MarcaSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Regla de negocio: No permitir borrar la marca por defecto
        if instance.nombre_marca == "Sin Marca":
            return Response(
                {"detail": "No se puede eliminar la marca 'Sin Marca'."},
                status=status.HTTP_403_FORBIDDEN
            )
        logging.info(f"Admin '{request.user}' borrando Marca: {instance.nombre_marca}")
        return super().destroy(request, *args, **kwargs)
    
@require_POST
@login_required
def draw_event(request, event_id):
    """
    Sortea 'amigo secreto' en el evento y envía un mensaje PRIVADO
    a cada participante con la persona que le tocó.
    Requisitos:
      - Evento con una conversacion de tipo 'evento'
      - >= 2 participantes
    """
    try:
        evento = Evento.objects.select_related('conversacion').get(pk=event_id)
    except Evento.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'evento_no_existe'}, status=404)

    # Seguridad: sólo participantes del evento pueden sortear
    es_participante = ParticipanteConversacion.objects.filter(
        conversacion=evento.conversacion, usuario=request.user
    ).exists()
    if not es_participante and request.user != evento.creador:
        return JsonResponse({'ok': False, 'error': 'sin_permiso'}, status=403)

    # La conversacion del evento debe existir
    if not evento.conversacion_id:
        return JsonResponse({'ok': False, 'error': 'evento_sin_conversacion'}, status=500)

    # Participantes del evento
    parts_qs = ParticipanteConversacion.objects.filter(
        conversacion=evento.conversacion
    ).select_related('usuario')

    usuarios = [p.usuario for p in parts_qs]
    if len(usuarios) < 2:
        return JsonResponse({'ok': False, 'error': 'participantes_insuficientes'}, status=400)

    # Derangement simple (evitar que alguien se asigne a sí mismo)
    givers = usuarios[:]
    receivers = usuarios[:]
    for _ in range(30):
        random.shuffle(receivers)
        if all(g != r for g, r in zip(givers, receivers)):
            break
    else:
        # Fallback seguro (rotación)
        receivers = usuarios[1:] + usuarios[:1]

    # Evitar repetir sorteo si ya se efectuó (opcional)
    if getattr(evento, 'sorteado', False):
        return JsonResponse({'ok': False, 'error': 'ya_sorteado'}, status=400)

    with transaction.atomic():
        # Marca de control (si tu modelo no tiene campo, puedes omitir)
        if hasattr(evento, 'sorteado'):
            evento.sorteado = True
        if hasattr(evento, 'fecha_sorteo'):
            evento.fecha_sorteo = timezone.now()
        evento.save(update_fields=[f for f in ['sorteado','fecha_sorteo'] if hasattr(evento, f)])

        # Enviar mensaje PRIVADO a cada participante
        # Lo enviaremos desde el "creador" del evento (o el usuario que sorteó)
        emisor = request.user

        for giver, receiver in zip(givers, receivers):
            conv_priv = get_or_create_direct_chat(emisor, giver)
            # Crea mensaje privado solo visible en el chat 1:1 con "giver"
            Mensaje.objects.create(
                conversacion=conv_priv,
                autor=emisor,
                contenido=f"🎁 Te tocó: {receiver.first_name or receiver.username}",
                tipo='sistema'  # usa el tipo que manejes para mensajes de sistema
            )

        # Mensaje público en el chat del evento (opcional)
        Mensaje.objects.create(
            conversacion=evento.conversacion,
            autor=emisor,
            contenido="🔒 El sorteo fue realizado. Cada uno recibió su asignación por privado.",
            tipo='sistema'
        )

    return JsonResponse({'ok': True})    

@api_view(['GET'])  
@permission_classes([IsAdminUser])  
def download_popular_search_report_pdf(request):
    """
    Genera un PDF con un gráfico de barras de las búsquedas populares
    y una tabla de datos.
    """
    try:
        # [cite_start]1. Obtener los datos (la misma consulta que tu API [cite: 369])
        search_data_qs = (
            HistorialBusqueda.objects
            .annotate(term_lower=Lower(Trim('term')))
            .values('term_lower')
            .annotate(count=Count('id_search'))
            .order_by('-count')[:20] # Tomamos los Top 20 para el gráfico
        )
        search_data = list(search_data_qs)

        image_base64 = None
        
        if search_data:
            # 2. Preparar datos para el gráfico
            # Convertimos los datos a un DataFrame de Pandas para graficar fácil
            df = pd.DataFrame(search_data)
            # Ordenamos para el gráfico de barras horizontal (el más alto primero)
            df = df.sort_values(by='count', ascending=True)

            # 3. Generar el Gráfico con Matplotlib
            plt.figure(figsize=(10, 8)) # Tamaño del gráfico (ancho, alto)
            
            # Gráfico de barras horizontal
            plt.barh(df['term_lower'], df['count'], color='#007bff') 
            
            plt.title('Top 20 Búsquedas Populares', fontsize=16)
            plt.xlabel('Número de Búsquedas', fontsize=12)
            plt.ylabel('Término de Búsqueda', fontsize=12)
            
            # Añadir los números al final de cada barra
            for index, value in enumerate(df['count']):
                plt.text(value, index, f' {value}', va='center')

            plt.tight_layout() # Ajusta para que no se corten las etiquetas

            # 4. Guardar el gráfico en un buffer de memoria
            buf = BytesIO()
            plt.savefig(buf, format='png')
            plt.close() # Cierra la figura para liberar memoria
            buf.seek(0)

            # 5. Codificar la imagen en Base64 para el HTML
            image_base64 = base64.b64encode(buf.read()).decode('utf-8')
            buf.close()

        # 6. Renderizar el template HTML
        template = get_template('reports/popular_search_report_pdf.html')
        context = {
            'search_data': search_data, # Los datos para la tabla
            'image_base64': image_base64, # La imagen del gráfico
            'generation_date': timezone.now()
        }
        html = template.render(context)
        
        # 7. Convertir HTML a PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)

        # 8. Devolver la respuesta PDF
        if not pdf.err:
            filename = f"reporte_busquedas_{datetime.date.today()}.pdf"
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        else:
            print(f"Error generando PDF de búsquedas: {pdf.err}")
            return Response({"error": "No se pudo generar el reporte PDF."}, status=500)

    except Exception as e:
        print(f"Error excepcional generando PDF de búsquedas: {e}")
        # Loggear el error completo en tu log de servidor
        logging.error(f"Error al generar PDF de búsquedas: {e}", exc_info=True)
        return Response({"error": f"No se pudo generar el reporte PDF: {e}"}, status=500)
    

@login_required
def api_post_comments(request, post_id):
    """
    Devuelve en JSON todos los comentarios de un post.
    Si viene ?filtro_malas_palabras=1 en la URL, censura el texto.
    Lo usa el modal de comentarios en el feed.
    """
    post = get_object_or_404(Post, id_post=post_id)
    comentarios = (
        post.comentarios
        .select_related('usuario__perfil')
        .order_by('fecha_comentario')
    )

    usar_filtro = request.GET.get("filtro_malas_palabras") == "1"
    MAX_COMMENTS_AI = 40  # límite global para no matar la API

    comentarios_list = list(comentarios)

    if usar_filtro:
        for idx, c in enumerate(comentarios_list):
            if idx < MAX_COMMENTS_AI:
                visible = censurar_con_openai(c.contenido or "")
            else:
                visible = c.contenido
            c._contenido_visible = visible
    else:
        for c in comentarios_list:
            c._contenido_visible = c.contenido

    data = {
        "comentarios": [
            {
                "id": c.id_comentario,
                "autor": c.usuario.nombre_usuario,
                "contenido": c._contenido_visible,  # 👈 ya viene censurado si corresponde
                "fecha": c.fecha_comentario.strftime("%d %b, %Y %H:%M"),
                "autor_foto": (
                    c.usuario.perfil.profile_picture.url
                    if hasattr(c.usuario, "perfil") and c.usuario.perfil.profile_picture
                    else None
                ),
                "es_propietario": (c.usuario_id == request.user.id),
            }
            for c in comentarios_list
        ]
    }
    return JsonResponse(data)


def _model_has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())

@require_http_methods(["GET", "POST"])
def resend_verification_view(request):
    if request.method == "POST":
        email_input = (request.POST.get("email") or "").strip().lower()
        if not email_input:
            messages.error(request, "Ingresa tu correo.")
            return redirect("resend_verification")

        User = get_user_model()
        user = User.objects.filter(correo__iexact=email_input).first()  # tu campo es 'correo'

        # Mensaje neutro SIEMPRE (no revelamos si existe)
        success_msg = "Si el correo existe, te enviamos un nuevo enlace de verificación."

        if not user:
            print("[RESEND] No existe usuario con ese correo (mensaje neutro mostrado).")
            messages.success(request, success_msg)
            return redirect("verification_sent")  # misma UX que el registro

        # Si YA está verificado, lo mandamos a login
        if getattr(user, "is_verified", False):
            print(f"[RESEND] Usuario {user.id} ya verificado.")
            messages.info(request, "Tu correo ya está verificado. Inicia sesión.")
            return redirect("account_login")

        # (Re)generar token SIEMPRE para garantizar link fresco
        try:
            user.verification_token = uuid.uuid4()
            user.token_created_at = timezone.now()
            user.save(update_fields=["verification_token", "token_created_at"])
            print(f"[RESEND] Token regenerado para user_id={user.id}")
        except Exception as e:
            # Si tu modelo tiene otros nombres de campos, ajusta arriba
            print(f"[RESEND][ERROR] No se pudo regenerar token para user_id={getattr(user,'id',None)} -> {e}")

        try:
            # Reusar exactamente el MISMO helper que usas al registrarse
            # (el que renderiza templates y arma verification_url)
            send_verification_email(user, request)
            print(f"[RESEND] Email de verificación reenviado a {email_input}")
        except Exception as e:
            # Logueamos pero devolvemos mensaje neutro
            print(f"[RESEND][ERROR] Falló send_verification_email -> {e}")

        messages.success(request, success_msg)
        return redirect("verification_sent")

    # GET
    return render(request, "account/resend_verification.html")

from core.models import ProductoExterno

def producto_externo_detalle(request, pk):
    producto = get_object_or_404(ProductoExterno, pk=pk)

    # Opcional: “similares” por categoría
    similares = (
        ProductoExterno.objects
        .filter(categoria__iexact=producto.categoria)
        .exclude(pk=pk)[:6]
    )

    context = {
        "producto": producto,          # ojo: aquí se llama igual que en tu template interno
        "similares": similares,
    }
    return render(request, "producto_externo_detalle.html", context)


@login_required
@require_POST
def favoritos_toggle_externo(request, producto_externo_id):
    from core.models import ProductoExterno, ProductoExternoFavorito

    try:
        producto = ProductoExterno.objects.get(pk=producto_externo_id)
    except ProductoExterno.DoesNotExist:
        return JsonResponse({"error": "Producto externo no encontrado"}, status=404)

    fav, created = ProductoExternoFavorito.objects.get_or_create(
        user=request.user,
        producto_externo=producto
    )

    if not created:
        # Ya existía → eliminarlo
        fav.delete()
        return JsonResponse({"state": "removed"})

    # Si se agregó → devolver respuesta
    return JsonResponse({"state": "added"})




def producto_externo_detalle(request, id_externo):
    """
    Redirige al detalle del Producto interno asociado a un ProductoExterno.
    Si no existe, lo crea automáticamente.
    """
    externo = get_object_or_404(ProductoExterno, pk=id_externo)
    producto = externo.ensure_producto_interno()
    return redirect("producto_detalle", id_producto=producto.id_producto)

