from itertools import count
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.conf import settings
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

from django.db.models import Prefetch, Q
from core.models import Wishlist, ItemEnWishlist
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from core.models import User, SolicitudAmistad, Seguidor, Evento  
from .serializers import SolicitudAmistadSerializer, UsuarioLiteSerializer
from .models import Conversacion, Mensaje, ParticipanteConversacion, EntregaMensaje
from .serializers import ConversacionSerializer, MensajeSerializer

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
# ajusta imports según tu app
from core.models import Evento, Post, Seguidor, SolicitudAmistad
from rest_framework.pagination import PageNumberPagination
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.models import Wishlist, ItemEnWishlist  


from core.models import Conversacion, Mensaje, ParticipanteConversacion
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





def home(request):
    try:
        productos_destacados = Producto.objects.filter(activo=True).order_by('-fecha_creacion')[:9]
        categorias = Categoria.objects.filter(producto__activo=True).distinct().order_by('nombre_categoria')[:12]

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

        context = {
            'productos_destacados': productos_destacados,
            'categorias': categorias,
            'amigos': amigos,
            'sugerencias': sugerencias,
            'solicitudes_recibidas': recibidas,   
            'solicitudes_enviadas': enviadas,   
            'favoritos_ids': favoritos_ids,  
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

    
def productos_list(request):
    """Vista para listar todos los productos activos"""
    query = request.GET.get('q', '')
    categoria_id = request.GET.get('categoria', '')
    marca_id = request.GET.get('marca', '')

    productos = Producto.objects.filter(activo=True)

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

    # Ordenar por rating promedio
    productos = productos.annotate(avg_rating=Avg('resenas__calificacion')).order_by('-avg_rating')

    # Paginación
    paginator = Paginator(productos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categorias = Categoria.objects.all()
    marcas = Marca.objects.all()

    # === NUEVO: ids de productos favoritos del usuario ===
    favoritos_ids = set()
    if request.user.is_authenticated:
        wl = get_default_wishlist(request.user)
        favoritos_ids = set(
            ItemEnWishlist.objects
            .filter(id_wishlist=wl)
            .values_list('id_producto', flat=True)
        )

    context = {
        'productos': page_obj,
        'categorias': categorias,
        'marcas': marcas,
        'query': query,
        'selected_categoria': categoria_id,
        'selected_marca': marca_id,
        'favoritos_ids': favoritos_ids,  # <--- NUEVO
    }
    return render(request, 'productos_list.html', context)


def producto_detalle(request, producto_id):
    """Vista para detalle de producto"""
    producto = get_object_or_404(Producto, id_producto=producto_id, activo=True)
    reseñas = producto.resenas.select_related('id_usuario').order_by('-fecha_resena')[:5]
    
    # Productos similares (misma categoría)
    productos_similares = Producto.objects.filter(
        id_categoria=producto.id_categoria,
        activo=True
    ).exclude(id_producto=producto_id)[:4]
    
    context = {
        'producto': producto,
        'reseñas': reseñas,
        'productos_similares': productos_similares,
    }
    return render(request, 'productos/detalle.html', context)

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
    """Búsqueda avanzada de productos"""
    query = request.GET.get('q', '')
    categoria_id = request.GET.get('categoria', '')
    marca_id = request.GET.get('marca', '')
    precio_min = request.GET.get('precio_min', '')
    precio_max = request.GET.get('precio_max', '')
    rating_min = request.GET.get('rating_min', '')
    
    productos = Producto.objects.filter(activo=True)
    
    # Filtros
    if query:
        productos = productos.filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query)
        )
    
    if categoria_id:
        productos = productos.filter(id_categoria_id=categoria_id)
    
    if marca_id:
        productos = productos.filter(id_marca_id=marca_id)
    
    if precio_min:
        productos = productos.filter(precio__gte=precio_min)
    
    if precio_max:
        productos = productos.filter(precio__lte=precio_max)
    
    # Filtrar por rating (necesita annotate)
    if rating_min:
        productos = productos.annotate(avg_rating=Avg('resenas__calificacion')).filter(
            avg_rating__gte=rating_min
        )
    
    # Ordenamiento
    orden = request.GET.get('orden', 'rating')
    if orden == 'precio_asc':
        productos = productos.order_by('precio')
    elif orden == 'precio_desc':
        productos = productos.order_by('-precio')
    elif orden == 'nombre':
        productos = productos.order_by('nombre_producto')
    else:  # rating por defecto
        productos = productos.annotate(avg_rating=Avg('resenas__calificacion')).order_by('-avg_rating')
    
    # Paginación
    paginator = Paginator(productos, 12)
    page_number = request.GET.get('page')
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
    }
    return render(request, 'productos/buscar.html', context)

def buscar_sugerencias(request):
    """Vista para obtener sugerencias de búsqueda en tiempo real"""
    query = request.GET.get('q', '').strip()
    print(f"🔍 Búsqueda recibida: '{query}'")  # Para debug
    
    if len(query) < 2:
        return JsonResponse({'sugerencias': []})
    
    sugerencias = []
    
    try:
        # Buscar productos por nombre, descripción o marca
        productos = Producto.objects.filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(id_marca__nombre_marca__icontains=query),
            activo=True
        ).select_related('id_categoria', 'id_marca')[:6]
        
        print(f"📦 Productos encontrados: {productos.count()}")  # Para debug
        
        for producto in productos:
            sugerencias.append({
                'tipo': 'producto',
                'texto': producto.nombre_producto,
                'marca': producto.id_marca.nombre_marca if producto.id_marca else '',
                'categoria': producto.id_categoria.nombre_categoria if producto.id_categoria else '',
                'url': f"/producto/{producto.id_producto}/"
            })
        
        # Buscar categorías
        categorias = Categoria.objects.filter(
            nombre_categoria__icontains=query
        )[:3]
        
        for categoria in categorias:
            sugerencias.append({
                'tipo': 'categoría',
                'texto': categoria.nombre_categoria,
                'descripcion': categoria.descripcion,
                'url': f"/productos/?categoria={categoria.id_categoria}"
            })
        
        # Buscar marcas
        marcas = Marca.objects.filter(
            nombre_marca__icontains=query
        )[:2]
        
        for marca in marcas:
            sugerencias.append({
                'tipo': 'marca', 
                'texto': marca.nombre_marca,
                'url': f"/productos/?marca={marca.id_marca}"
            })
            
    except Exception as e:
        print(f"❌ Error en búsqueda de sugerencias: {e}")
    
    print(f"🎯 Total sugerencias a enviar: {len(sugerencias)}")  # Para debug
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

    eventos = (Evento.objects
               .filter(id_usuario=request.user)
               .order_by('fecha_evento', 'evento_id'))

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

    amigos = User.objects.filter(id__in=ids_amigos)\
             .select_related('perfil')\
             .order_by('nombre', 'apellido')
    
    wl = get_default_wishlist(request.user)

    # ⬇️ PEQUEÑO ajuste: sólo items NO recibidos en la wishlist
    wishlist_items = (
        ItemEnWishlist.objects
        .filter(id_wishlist=wl, fecha_comprado__isnull=True)
        .select_related('id_producto', 'id_producto__id_marca')
        .prefetch_related('id_producto__urls_tienda')
        .order_by('-id_item')
    )

    # ⬇️ NUEVO: items YA recibidos para la pestaña "Regalos recibidos"
    recibidos_items = (
        ItemEnWishlist.objects
        .filter(id_wishlist=wl, fecha_comprado__isnull=False)
        .select_related('id_producto', 'id_producto__id_marca')
        .prefetch_related('id_producto__urls_tienda')
        .order_by('-fecha_comprado', '-id_item')
    )

    favoritos_ids = set(
        wishlist_items.values_list('id_producto', flat=True)
    )

    context = {
        'perfil': perfil,
        'prefs': prefs,
        'eventos': eventos,
        'evento_form': evento_form,
        'amigos': amigos, 
        'wishlist_items': wishlist_items,
        'favoritos_ids': favoritos_ids,
        'recibidos_items': recibidos_items,
    }
    return render(request, 'perfil.html', context)



@login_required
def profile_edit(request):
    """
    Edita: datos del User (nombre, apellido, nombre_usuario),
    más Perfil (bio, foto, birth_date) y Preferencias.
    """
    user = request.user
    perfil, _ = Perfil.objects.get_or_create(user=user)
    prefs, _ = PreferenciasUsuario.objects.get_or_create(user=user)

    if request.method == 'POST':
        u_form   = ProfileEditForm(request.POST, instance=user)
        p_form   = PerfilForm(request.POST, request.FILES, instance=perfil)
        pref_form = PreferenciasUsuarioForm(request.POST, instance=prefs)

        if u_form.is_valid() and p_form.is_valid() and pref_form.is_valid():
            u = u_form.save()      # guarda nombre/apellido/nombre_usuario (con unicidad)
            p_form.save()
            pref_form.save()
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('perfil')  # o a donde corresponda
        else:
            messages.error(request, 'Revisa los campos marcados.')
    else:
        u_form   = ProfileEditForm(instance=user)
        p_form   = PerfilForm(instance=perfil)
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
    def get(self, request):
        qs = (Conversacion.objects
              .filter(participantes__usuario=request.user)
              .select_related("ultimo_mensaje__remitente__perfil")
              .prefetch_related("participantes__usuario__perfil")
              .order_by("-actualizada_en")
              .distinct())
        data = ConversacionLiteSerializer(qs, many=True).data
        return Response(data)


class MensajesListCreate(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = SmallPagination

    def get_conv(self, request, conv_id):
        try:
            conv = (Conversacion.objects
                    .prefetch_related("participantes__usuario__perfil")  # <-- añade __perfil
                    .get(conversacion_id=conv_id, participantes__usuario=request.user))
        except Conversacion.DoesNotExist:
            return None
        return conv

    def get(self, request, conv_id):
        conv = self.get_conv(request, conv_id)
        if not conv:
            return Response({"detail": "Conversación no encontrada"}, status=404)

        qs = (Mensaje.objects
              .filter(conversacion=conv)
              .select_related("remitente__perfil")   # ⬅️ importante
              .order_by("-creado_en"))

        paginator = SmallPagination()
        page = paginator.paginate_queryset(qs, request)
        ser = MensajeSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)

    def post(self, request, conv_id):
        conv = self.get_conv(request, conv_id)
        if not conv:
            return Response({"detail": "Conversación no encontrada"}, status=404)

        contenido = (request.data.get("contenido") or "").strip()
        if not contenido:
            return Response({"detail": "contenido es requerido"}, status=400)

        msg = Mensaje.objects.create(
            conversacion=conv,
            remitente=request.user,
            contenido=contenido,
            tipo=Mensaje.Tipo.TEXTO,
        )
        # actualiza puntero y timestamp de conversación
        conv.ultimo_mensaje = msg
        conv.save(update_fields=["ultimo_mensaje", "actualizada_en"])

        # (Opcional) emitir por WebSocket al grupo de la sala
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{conv.conversacion_id}",
                {"type": "chat.message", "message": contenido,
                 "user": getattr(request.user, "nombre_usuario", "usuario")}
            )
        except Exception:
            pass

        return Response(MensajeSerializer(msg).data, status=201)                



##nuevas funciones hoy 1 del 10 (abajo):
@login_required
def amistad_enviar(request, username):
    User = get_user_model()
    receptor = get_object_or_404(User, nombre_usuario=username)
    if receptor == request.user:
        messages.warning(request, "No puedes enviarte una solicitud a ti mismo.")
        return redirect('home')  # o 'index' si así se llama tu url de inicio

    # Respetamos tu UniqueConstraint (emisor, receptor)
    try:
        with transaction.atomic():
            SolicitudAmistad.objects.create(
                emisor=request.user, receptor=receptor, mensaje=""
            )
            messages.success(request, f"Solicitud enviada a {receptor.nombre}.")
    except IntegrityError:
        messages.info(request, "Ya existe una solicitud o relación con este usuario.")
    return redirect('home')


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
    conv = sol.aceptar()  # usa tu método: follow mutuo + crea Conversacion directa
    messages.success(request, f"Ahora eres amigo de {emisor.nombre}.")
    # si quieres llevar al chat inmediatamente:
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
    messages.info(request, "Solicitud cancelada.")
    return redirect('home')


@login_required
def chat_con_usuario(request, username):
    User = get_user_model()
    other = get_object_or_404(User, nombre_usuario=username)
    conv = obtener_o_crear_conv_directa(request.user, other)  # por si entran desde “Amigos”
    return redirect('chat_room', conversacion_id=conv.conversacion_id)        


from django.db.models import Prefetch  # ya lo tienes importado arriba

def perfil_publico(request, username):
    User = get_user_model()
    usuario = get_object_or_404(User, nombre_usuario=username)

    # Si es tu propio perfil → redirige a tu perfil
    if request.user.is_authenticated and request.user.id == usuario.id:
        return redirect('perfil')

    perfil = getattr(usuario, 'perfil', None)

    es_mi_perfil = False
    es_amigo = False
    pendiente_enviada = None
    pendiente_recibida = None
    puede_chatear = False

    if request.user.is_authenticated:
        sigo = Seguidor.objects.filter(seguidor=request.user, seguido=usuario).exists()
        me_sigue = Seguidor.objects.filter(seguidor=usuario, seguido=request.user).exists()
        es_amigo = sigo and me_sigue                 # ← OJO: "and", NUNCA "&&"
        puede_chatear = es_amigo

        pendiente_enviada = SolicitudAmistad.objects.filter(
            emisor=request.user, receptor=usuario, estado=SolicitudAmistad.Estado.PENDIENTE
        ).first()
        pendiente_recibida = SolicitudAmistad.objects.filter(
            emisor=usuario, receptor=request.user, estado=SolicitudAmistad.Estado.PENDIENTE
        ).first()

    eventos_publicos = (
        Evento.objects
        .filter(id_usuario=usuario)
        .order_by('fecha_evento')
    )

    ultimos_posts = (
        Post.objects
        .filter(id_usuario=usuario, es_publico=True)
        .order_by('-fecha_publicacion')[:6]
    )

    # Wishlist pública (solo si son amigos)
    wl = Wishlist.objects.filter(usuario=usuario).first()
    wishlist_items_publicos = []
    if wl and es_amigo:
        wishlist_items_publicos = (
            ItemEnWishlist.objects
            # ⇩⇩⇩ SOLO PENDIENTES (NO RECIBIDOS)
            .filter(id_wishlist=wl, fecha_comprado__isnull=True)
            # Si además tienes un booleano 'recibido', podrías añadir (opcional):
            # .filter(Q(recibido=False) | Q(recibido__isnull=True))
            .select_related('id_producto', 'id_producto__id_marca')
            .prefetch_related('id_producto__urls_tienda')
            .order_by('-pk')
        )

    # Recibidos públicos (visible para cualquiera)
    recibidos_publicos = []
    if wl:
        recibidos_publicos = (
            ItemEnWishlist.objects
            .filter(id_wishlist=wl, fecha_comprado__isnull=False)   # clave
            .select_related('id_producto', 'id_producto__id_marca')
            .prefetch_related(Prefetch('id_producto__urls_tienda'))
            .order_by('-fecha_comprado', '-pk')
        )

    context = {
        'usuario_publico': usuario,
        'perfil_publico': perfil,
        'es_mi_perfil': es_mi_perfil,
        'es_amigo': es_amigo,
        'pendiente_enviada': pendiente_enviada,
        'pendiente_recibida': pendiente_recibida,
        'puede_chatear': puede_chatear,
        'ultimos_posts': ultimos_posts,
        'eventos_publicos': eventos_publicos,
        'wishlist_items_publicos': wishlist_items_publicos,
        'recibidos_publicos': recibidos_publicos,
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
    contenido = (request.POST.get('contenido') or '').strip()
    if not contenido:
        return redirect(_next_url(request))  # vuelve a donde estabas

    post = Post.objects.create(
        id_usuario=request.user,   # ajusta si tu FK se llama distinto
        contenido=contenido
    )

    # Base a donde volver (form.next o referer o 'feed')
    base = _next_url(request)
    # quita cualquier ancla previa y agrega la del post nuevo
    base = base.split('#', 1)[0]
    return redirect(f'{base}#post-{post.id_post}')
    
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

        