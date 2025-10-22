from itertools import count
from django.templatetags.static import static
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.conf import settings
from core.services.gifter_ai import generar_sugerencias_regalo
from core.services.recommendations import recommend_when_wishlist_empty
from .forms import PostForm, RegisterForm, PerfilForm, PreferenciasUsuarioForm, EventoForm
from .models import *
from .emails import send_verification_email, send_welcome_email
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.urls import reverse
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
from django.shortcuts import get_object_or_404
from .models import User, Post, Like  # ajusta si necesitas más
from core.forms import ProfileEditForm
from .utils import get_default_wishlist
from django.db.models import Q, Avg, Case, When
import openai
from django.db.models import Prefetch, Q
from core.models import Wishlist, ItemEnWishlist
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from core.models import User, SolicitudAmistad, Seguidor, Evento
from .serializers import SolicitudAmistadSerializer, UsuarioLiteSerializer
from .models import *
from .serializers import *
from core.models import Producto, Categoria, Marca
from core.search import meili
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render  # ajusta imports según tu app
from core.models import Evento, Post, Seguidor, SolicitudAmistad
from rest_framework.pagination import PageNumberPagination
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.models import Wishlist, ItemEnWishlist
from core.models import Conversacion, Mensaje, ParticipanteConversacion
from core.models import NotificationDevice, PreferenciasUsuario, Perfil
from .serializers import ConversacionLiteSerializer, MensajeSerializer
###nuevo hoy 1 del 10 (abajo)
from core.services_social import amigos_qs, sugerencias_qs, obtener_o_crear_conv_directa
from django.contrib.auth import get_user_model
from core.models import Post, Comentario
from django.utils.html import escape
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse  # puedes dejarlo, pero ya no dependemos de reverse en el fallback
from django.views.decorators.http import require_GET
from django.core.cache import cache
# Para Reseña
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from .forms import ResenaSitioForm
from .models import ResenaSitio
#########################

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Avg, Count
from django.core.files.storage import default_storage
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django.utils.text import get_valid_filename
import os, uuid
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

# Decoradores/permissions DRF
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser,IsAuthenticated

# Utilidades Django
from django.core.management import call_command
from rest_framework.authentication import SessionAuthentication, BasicAuthentication


from django.db import transaction
from .models import Conversacion


# Stdlib
import traceback

# Formularios locales (solo si tienes una vista de contacto que lo use)
from .forms import ContactForm
User = get_user_model()


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
    try:
        productos_destacados = Producto.objects.filter(activo=True).order_by('-fecha_creacion')[:9]
        categorias = (Categoria.objects
                      .filter(producto__activo=True)
                      .distinct()
                      .order_by('nombre_categoria')[:12])

        amigos = []
        sugerencias = []
        recibidas = []
        enviadas = []
        favoritos_ids = set()

        if request.user.is_authenticated:
            amigos = amigos_qs(request.user)
            sugerencias = sugerencias_qs(request.user, limit=9)
            recibidas = (SolicitudAmistad.objects
                         .filter(receptor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE)
                         .select_related('emisor')
                         .order_by('-creada_en')[:10])
            enviadas = (SolicitudAmistad.objects
                        .filter(emisor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE)
                        .select_related('receptor')
                        .order_by('-creada_en')[:10])

            wl = get_default_wishlist(request.user)
            favoritos_ids = set(
                ItemEnWishlist.objects
                .filter(id_wishlist=wl)
                .values_list('id_producto', flat=True)
            )

        # === Reseñas del sitio (últimas 6) ===
        try:
            # Si tienes Perfil (OneToOne) y quieres evitar N+1, descomenta la siguiente línea:
            # resenas = (ResenaSitio.objects.select_related('id_usuario', 'id_usuario__perfil')
            resenas = (ResenaSitio.objects
                       .select_related('id_usuario')
                       .order_by('-fecha_resena')[:6])
        except Exception:
            resenas = []

        # === Tu reseña (para mostrar botones y prellenar el form) ===
        own_resena = None
        if request.user.is_authenticated:
            own_resena = ResenaSitio.objects.filter(id_usuario=request.user).first()

        context = {
            'productos_destacados': productos_destacados,
            'categorias': categorias,
            'amigos': amigos,
            'sugerencias': sugerencias,
            'solicitudes_recibidas': recibidas,
            'solicitudes_enviadas': enviadas,
            'favoritos_ids': favoritos_ids,
            'resenas': resenas,
            'own_resena': own_resena,  # <- nuevo
        }
        return render(request, 'index.html', context)

    except Exception:
        return render(request, 'index.html', {
            'productos_destacados': [],
            'categorias': [],
            'amigos': [],
            'sugerencias': [],
            'solicitudes_recibidas': [],
            'solicitudes_enviadas': [],
            'favoritos_ids': set(),
            'resenas': [],
            'own_resena': None,  # <- nuevo en fallback
        })


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
    """
    Alterna un producto en la wishlist 'Favoritos' del usuario:
    - Si existe, lo quita.
    - Si no existe, lo agrega con cantidad=1.
    """
    producto = get_object_or_404(Producto, pk=product_id, activo=True)
    wl = get_default_wishlist(request.user)

    item = ItemEnWishlist.objects.filter(id_wishlist=wl, id_producto=producto).first()
    if item:
        item.delete()
        state = "removed"
    else:
        # Requiere que ItemEnWishlist.cantidad use MinValueValidator(1)
        ItemEnWishlist.objects.create(id_wishlist=wl, id_producto=producto, cantidad=1)
        state = "added"

    return JsonResponse({"status": "ok", "state": state, "product_id": product_id})

    
from django.db.models import Q
from django.core.paginator import Paginator

def productos_list(request):
    """Lista de productos activos con filtros (sin dependencia de 'resenas')."""
    query = (request.GET.get('q') or '').strip()
    categoria_id = (request.GET.get('categoria') or '').strip()
    marca_id = (request.GET.get('marca') or '').strip()
    orden = request.GET.get('orden', 'recientes')  # recientes | precio_asc | precio_desc | nombre

    productos = Producto.objects.filter(activo=True)

    # Filtros
    if query:
        productos = productos.filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(id_marca__nombre_marca__icontains=query)
        )
    if categoria_id:
        productos = productos.filter(id_categoria_id=categoria_id)
    if marca_id:
        productos = productos.filter(id_marca_id=marca_id)

    # Orden (sin 'resenas')
    if orden == 'precio_asc':
        productos = productos.order_by('precio')
    elif orden == 'precio_desc':
        productos = productos.order_by('-precio')
    elif orden == 'nombre':
        productos = productos.order_by('nombre_producto')
    else:  # recientes
        productos = productos.order_by('-fecha_creacion', '-id_producto')

    # Paginación
    paginator = Paginator(productos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categorias = Categoria.objects.all()
    marcas = Marca.objects.all()

    # Favoritos del usuario (si está logueado)
    favoritos_ids = set()
    if request.user.is_authenticated:
        wl = get_default_wishlist(request.user)
        favoritos_ids = set(
            ItemEnWishlist.objects
            .filter(id_wishlist=wl)
            .values_list('id_producto', flat=True)
        )
        # ---- Personas que coinciden con la búsqueda ----
    personas_amigos, personas_otros = _people_matches(request, query)


    context = {
        'productos': page_obj,
        'categorias': categorias,
        'marcas': marcas,
        'query': query,
        'selected_categoria': categoria_id,
        'selected_marca': marca_id,
        'favoritos_ids': favoritos_ids,
        'orden': orden,
        'personas_amigos': personas_amigos,
        'personas_otros': personas_otros,
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
##TODo LO QUE TENGA QUE VER CON EL FEED AQUI
@login_required
def feed_view(request):
    """
    Versión original y optimizada para mostrar el feed y el estado de los 'likes'.
    """
    form = PostForm()

    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            nuevo_post = form.save(commit=False)
            nuevo_post.id_usuario = request.user
            nuevo_post.save()
            return redirect('feed')
    
    # 1. Obtenemos todos los posts, optimizando con prefetch_related para los likes
    all_posts = Post.objects.all().select_related('id_usuario').prefetch_related('likes').order_by('-fecha_publicacion')

    # 2. Obtenemos los IDs de los posts a los que el usuario actual ha dado like
    liked_post_ids = Like.objects.filter(
        id_usuario=request.user, 
        id_post__in=all_posts
    ).values_list('id_post_id', flat=True)
    
    # 3. Añadimos el atributo 'user_has_liked' a cada post
    for post in all_posts:
        post.user_has_liked = post.id_post in liked_post_ids

    context = {
        'posts': all_posts,
        'form': form
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
                sugerencias.append({
                    "tipo": "producto",
                    "texto": p.nombre_producto,
                    "marca": p.id_marca.nombre_marca if p.id_marca else "",
                    "categoria": p.id_categoria.nombre_categoria if p.id_categoria else "",
                    "url": f"/producto/{p.id_producto}/"
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
    perfil, _ = Perfil.objects.get_or_create(user=request.user)
    prefs, _ = PreferenciasUsuario.objects.get_or_create(user=request.user)

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

    # ===== Amigos (seguimiento mutuo) =====
    User = get_user_model()
    ids_yo_sigo   = Seguidor.objects.filter(seguidor=request.user)\
                      .values_list('seguido_id', flat=True)
    ids_me_siguen = Seguidor.objects.filter(seguido=request.user)\
                      .values_list('seguidor_id', flat=True)
    ids_amigos = set(ids_yo_sigo).intersection(set(ids_me_siguen))

    amigos = (
        User.objects.filter(id__in=ids_amigos)
        .select_related('perfil')
        .order_by('nombre', 'apellido')
    )

    wl = get_default_wishlist(request.user)

    # Wishlist: solo NO recibidos
    wishlist_items = (
        ItemEnWishlist.objects
        .filter(id_wishlist=wl, fecha_comprado__isnull=True)
        .select_related('id_producto', 'id_producto__id_marca')
        .prefetch_related('id_producto__urls_tienda')
        .order_by('-id_item')
    )

    # Recibidos (para pestaña "Regalos recibidos")
    recibidos_items = (
        ItemEnWishlist.objects
        .filter(id_wishlist=wl, fecha_comprado__isnull=False)
        .select_related('id_producto', 'id_producto__id_marca')
        .prefetch_related('id_producto__urls_tienda')
        .order_by('-fecha_comprado', '-id_item')
    )

    # ==== Solicitudes (mismos nombres que en index) ====
    solicitudes_recibidas = (
        SolicitudAmistad.objects
        .filter(receptor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE)
        .select_related('emisor', 'emisor__perfil')
        .order_by('-creada_en')
    )
    solicitudes_enviadas = (
        SolicitudAmistad.objects
        .filter(emisor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE)
        .select_related('receptor', 'receptor__perfil')
        .order_by('-creada_en')
    )
    sol_pendientes_count = solicitudes_recibidas.count()

    favoritos_ids = set(wishlist_items.values_list('id_producto', flat=True))

    context = {
        'perfil': perfil,
        'prefs': prefs,
        'eventos': eventos,
        'evento_form': evento_form,
        'amigos': amigos,
        'wishlist_items': wishlist_items,
        'favoritos_ids': favoritos_ids,
        'recibidos_items': recibidos_items,

        # ← nombres idénticos a index.html
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
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('perfil')
        else:
            messages.error(request, 'Revisa los campos marcados.')
    else:
        u_form    = ProfileEditForm(instance=user)
        p_form    = PerfilForm(instance=perfil)
        pref_form = PreferenciasUsuarioForm(instance=prefs)



    return render(request, 'perfil_editar.html', {
        'u_form': u_form,
        'p_form': p_form,
        'pref_form': pref_form,
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

        # MENSAJE DE IMAGEN
        if tipo == Mensaje.Tipo.IMAGEN:
            up = request.FILES.get("archivo")
            if not up:
                return Response({"detail": "archivo es requerido"}, status=400)

            # guarda en /media/chat/
            orig = get_valid_filename(up.name or "image")
            ext = os.path.splitext(orig)[1].lower() or ".jpg"
            name = f"chat/{uuid.uuid4().hex}{ext}"
            path = default_storage.save(name, up)
            url = default_storage.url(path)

            msg = Mensaje.objects.create(
                conversacion=conv,
                remitente=request.user,
                tipo=Mensaje.Tipo.IMAGEN,
                contenido=contenido,                # pie de foto opcional
                metadatos={"archivo_url": url},
            )
        else:
            # TEXTO (default)
            if not contenido:
                return Response({"detail": "contenido es requerido"}, status=400)
            msg = Mensaje.objects.create(
                conversacion=conv,
                remitente=request.user,
                tipo=Mensaje.Tipo.TEXTO,
                contenido=contenido,
            )

        # actualizar puntero de la conversación
        conv.ultimo_mensaje = msg
        conv.save(update_fields=["ultimo_mensaje", "actualizada_en"])

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

    # 👇 Responder JSON si es AJAX
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



def perfil_publico(request, username):
    usuario = get_object_or_404(User, nombre_usuario=username)

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

    eventos_publicos = Evento.objects.filter(id_usuario=usuario).order_by('fecha_evento')
    ultimos_posts = Post.objects.filter(id_usuario=usuario, es_publico=True).order_by('-fecha_publicacion')[:6]

    wl = Wishlist.objects.filter(usuario=usuario).first()
    wishlist_items_publicos = ItemEnWishlist.objects.none()
    recibidos_publicos = ItemEnWishlist.objects.none()

    # NUEVO: contenedores
    sugerencias_ia_lista = []
    recomendados = []

    print(f"[DEBUG] perfil_publico para {username}. Es amigo: {es_amigo}. Wishlist encontrada: {'Sí' if wl else 'No'}")

    if wl:
        recibidos_publicos = (
            ItemEnWishlist.objects
            .filter(id_wishlist=wl, fecha_comprado__isnull=False)
            .select_related('id_producto', 'id_producto__id_marca')
            .prefetch_related(Prefetch('id_producto__urls_tienda', queryset=UrlTienda.objects.filter(activo=True)))
            .order_by('-fecha_comprado', '-pk')
        )

        if es_amigo:
            wishlist_items_publicos = (
                ItemEnWishlist.objects
                .filter(id_wishlist=wl, fecha_comprado__isnull=True)
                .filter(id_producto__activo=True)
                .select_related('id_producto', 'id_producto__id_marca')
                .prefetch_related(Prefetch('id_producto__urls_tienda', queryset=UrlTienda.objects.filter(activo=True)))
                .order_by('-pk')
            )

            wishlist_count = wishlist_items_publicos.count()
            print(f"[DEBUG] Conteo de wishlist_items_publicos (activos): {wishlist_count}")

            # --- RECOMENDADOR: si la wishlist activa está vacía ---
            if wishlist_count == 0:
                # 1) Productos REALES recomendados (según recibidos/wishlist histórica)
                cache_key_rec = f"reco_user_{usuario.id}"
                recomendados = cache.get(cache_key_rec, [])
                if not recomendados:
                    recomendados = recommend_when_wishlist_empty(usuario, limit=3)
                    cache.set(cache_key_rec, recomendados, 60 * 30)  # 30 min
                print(f"[RECO] Recomendados generados: {len(recomendados)}")

                # 2) (Opcional) IA como fallback SOLO si no encontramos candidatos
                if not recomendados:
                    datos_para_ia = ""
                    nombres_recibidos = [item.id_producto.nombre_producto for item in recibidos_publicos[:3]]
                    if nombres_recibidos:
                        datos_para_ia += f"Regalos que ha recibido antes: {', '.join(nombres_recibidos)}.\n"
                        print(f"[IA] Usando regalos recibidos: {nombres_recibidos}")
                    elif perfil and getattr(perfil, "bio", ""):
                        datos_para_ia += f"Su biografía: {perfil.bio}\n"
                        print(f"[IA] Usando biografía.")

                    if datos_para_ia:
                        cache_key_ia = f"ia_sugg_user_{usuario.id}"
                        sugerencias_ia_lista = cache.get(cache_key_ia, [])
                        if not sugerencias_ia_lista:
                            sugerencias_ia_lista = generar_sugerencias_regalo(usuario.nombre, datos_para_ia)
                            cache.set(cache_key_ia, sugerencias_ia_lista, 60 * 60)  # 1 hora
                        print(f"[IA] Sugerencias IA: {len(sugerencias_ia_lista)}")
            else:
                print(f"[DEBUG] La wishlist NO está vacía ({wishlist_count} items activos), saltando recomendaciones/IA.")

    # --- Contexto Final ---
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
        'recomendados': recomendados,          # NUEVO: productos reales sugeridos
        'sugerencias_ia': sugerencias_ia_lista # IA solo si no hubo recomendados
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
        
        # Asignar el tipo de post
        if form.cleaned_data.get('imagen'):
            post.tipo_post = Post.TipoPost.IMAGEN
        else:
            post.tipo_post = Post.TipoPost.TEXTO
            
        post.save()
        messages.success(request, "¡Publicación creada con éxito!")
    else:
        # Si el formulario no es válido, muestra un error
        # (puedes manejarlo de una forma más elegante si quieres)
        messages.error(request, "No se pudo crear la publicación. Revisa los datos.")

    return redirect(_next_url(request))
    
@login_required
def feed(request):
    # Si quieres súper simple: traes posts y el template usa post.comentarios.all
    posts = Post.objects.select_related('id_usuario__perfil').order_by('-fecha_publicacion')
    return render(request, 'feed/feed.html', {'posts': posts})

@login_required
@require_POST
def comentario_crear(request):
    post_id = request.POST.get('post_id')
    contenido = (request.POST.get('contenido') or '').strip()
    if not post_id or not contenido:
        return redirect(_next_url(request))  # vuelve al feed, no al index

    post = get_object_or_404(Post, pk=post_id)
    c = Comentario.objects.create(id_post=post, usuario=request.user, contenido=contenido)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        foto = getattr(getattr(request.user, 'perfil', None), 'profile_picture', None)
        return JsonResponse({
            'ok': True,
            'post_id': post.id_post,
            'comment': {
                'id': c.id_comentario,
                'nombre_usuario': request.user.nombre_usuario,
                'autor_foto': (foto.url if foto else None),
                'contenido': c.contenido,
                'creado_en': c.fecha_comentario.strftime('%d %b, %Y %H:%M'),
            }
        })
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

    # fecha formateada para pintarla sin recargar
    fecha_text = now.strftime('%d/%m/%Y %H:%M')
    return JsonResponse({'ok': True, 'item_id': item_id, 'fecha': fecha_text})


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
            from core.services_social import amigos_qs as amigos_func
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


#####################################################################
#####################################################################
#####################################################################

@login_required
def resena_sitio_crear(request):
    if request.method != "POST":
        return redirect("home")

    # bloquea duplicados: si ya tiene, pide usar editar
    if ResenaSitio.objects.filter(id_usuario=request.user).exists():
        messages.warning(request, "Ya tienes una reseña. Usa el botón Editar para actualizarla.")
        return redirect("home")

    form = ResenaSitioForm(request.POST)
    if form.is_valid():
        r = form.save(commit=False)
        r.id_usuario = request.user
        r.save()
        messages.success(request, "¡Gracias por tu reseña!")
    else:
        messages.error(request, "Revisa la calificación (1–5) y/o tu comentario.")
    return redirect(f"{reverse('home')}#testimonials")

@login_required
def resena_sitio_editar(request):
    if request.method != "POST":
        return redirect("home")

    # solo edita la reseña del usuario actual
    instancia = ResenaSitio.objects.filter(id_usuario=request.user).first()
    if not instancia:
        messages.warning(request, "Aún no tienes reseña para editar.")
        return redirect("home")

    form = ResenaSitioForm(request.POST, instance=instancia)
    if form.is_valid():
        form.save()
        messages.success(request, "¡Actualizamos tu reseña! ✨")
    else:
        messages.error(request, "Revisa la calificación (1–5) y/o tu comentario.")
    return redirect(f"{reverse('home')}#testimonials")


@login_required
def resena_sitio_eliminar(request):
    if request.method != "POST":
        return redirect("home")

    instancia = ResenaSitio.objects.filter(id_usuario=request.user).first()
    if not instancia:
        messages.warning(request, "No tienes reseña para eliminar.")
        return redirect("home")

    instancia.delete()
    messages.success(request, "Reseña eliminada.")
    return redirect(f"{reverse('home')}#testimonials")


#####################################################################
#####################################################################
#####################################################################


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

    # usa 'titulo' si existe, si no 'nombre'
    title = (getattr(conv, "titulo", None) or getattr(conv, "nombre", None) or "")  
    # deduce grupo por tipo o por cantidad de participantes
    tipo_val = getattr(conv, "tipo", "") or ""
    is_group = bool(
        getattr(conv, "is_group", False) or
        (tipo_val.lower() == "grupo") or
        (len(data_part) > 2)
    )

    return JsonResponse({
        "conversacion_id": getattr(conv, "conversacion_id", conv.pk),
        "is_group": is_group,
        "titulo": title,
        "participantes": data_part,
        "es_autor": (conv.creador_id == request.user.id),   # ← NECESARIO para mostrar ⋮
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
    
class ProductoListAPIView(generics.ListAPIView):
    """
    Vista de API para listar todos los productos (con paginación).
    Accesible en /api/productos/
    """
    queryset = Producto.objects.filter(activo=True) # Solo muestra productos activos
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]
    # DRF maneja la paginación automáticamente si está configurada en settings.py
    # Si no, puedes añadirla aquí:
    # from rest_framework.pagination import PageNumberPagination
    # pagination_class = PageNumberPagination
    
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

class UserDetailAPIView(generics.RetrieveUpdateAPIView): # Usamos RetrieveUpdate, no Destroy
    """
    Vista de API para ver y actualizar (parcial) un usuario específico.
    Accesible en /api/users/<int:pk>/
    Donde <int:pk> es el id del usuario.
    """
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser] # Solo admins pueden ver/editar usuarios
    lookup_field = 'pk' # El ID vendrá como 'pk' en la URL


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

    # normaliza y evita duplicados / self-joins existentes
    try:
        ids = [int(x) for x in ids]
    except Exception:
        return JsonResponse({'error': 'IDs inválidos'}, status=400)

    # ya participantes:
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

    return JsonResponse({"ok": True, "agregados": [u.id for u in users]})
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
def grupos_leave(request, pk):
    # 1) traer la conversación
    conv = get_object_or_404(Conversacion, pk=pk, is_group=True)

    # 2) el autor no puede "salir"; debe eliminar o transferir admin
    if getattr(conv, "creador_id", None) == request.user.id:
        return JsonResponse(
            {"ok": False, "error": "El autor no puede abandonar el grupo."},
            status=400
        )

    # 3) buscar la membresía
    try:
        miembro = ConversacionMiembro.objects.get(conversacion=conv, usuario=request.user)
    except ConversacionMiembro.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "No eres miembro de este grupo."},
            status=404
        )

    # 4) borrar membresía
    miembro.delete()

    # (opcional) si no quedan miembros, podés cerrar/eliminar el grupo
    # if not ConversacionMiembro.objects.filter(conversacion=conv).exists():
    #     conv.delete()

    return JsonResponse({"ok": True})