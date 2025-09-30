from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.conf import settings
from .forms import RegisterForm
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


from .models import User, Post, Like  # ajusta si necesitas más


def home(request):
    """Página principal con productos destacados"""
    try:
        # Obtener productos activos (máximo 9 para la página principal)
        productos_destacados = Producto.objects.filter(activo=True).order_by('-fecha_creacion')[:9]
        
        # Debug en consola
        print("🎯 VISTA HOME EJECUTADA")
        print(f"📦 Productos encontrados: {productos_destacados.count()}")
        for p in productos_destacados:
            print(f"   - {p.nombre_producto} (Imagen: {'Sí' if p.imagen else 'No'})")
        
        context = {
            'productos_destacados': productos_destacados,
        }
        return render(request, 'index.html', context)
        
    except Exception as e:
        print(f"❌ Error en vista home: {e}")
        import traceback
        print(traceback.format_exc())
        
        # En caso de error, mostrar lista vacía
        context = {
            'productos_destacados': [],
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
    
def productos_list(request):
    """Vista para listar todos los productos activos"""
    query = request.GET.get('q', '')
    categoria_id = request.GET.get('categoria', '')
    
    productos = Producto.objects.filter(activo=True)
    
    if query:
        productos = productos.filter(
            Q(nombre_producto__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(id_marca__nombre_marca__icontains=query)
        )
    
    if categoria_id:
        productos = productos.filter(id_categoria_id=categoria_id)
    
    # Ordenar por rating promedio
    productos = productos.annotate(avg_rating=Avg('resenas__calificacion')).order_by('-avg_rating')
    
    # Paginación
    paginator = Paginator(productos, 12)  # 12 productos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categorias = Categoria.objects.all()
    
    context = {
        'productos': page_obj,
        'categorias': categorias,
        'query': query,
        'selected_categoria': categoria_id,
    }
    return render(request, 'productos/list.html', context)

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

def feed_view(request):
    """
    Esta vista se encarga de mostrar el feed principal a los usuarios.
    """
    # Por ahora, solo renderizamos la plantilla.
    # Más adelante, aquí obtendremos los posts de la base de datos.
    context = {} # Un diccionario vacío por ahora
    return render(request, 'feed.html', context)

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

def productos_list(request):
    """Vista para listar todos los productos activos con filtros"""
    query = request.GET.get('q', '')
    categoria_id = request.GET.get('categoria', '')
    marca_id = request.GET.get('marca', '')
    
    productos = Producto.objects.filter(activo=True)
    
    # Aplicar filtros
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
    
    # Ordenar por fecha de creación (más recientes primero)
    productos = productos.order_by('-fecha_creacion')
    
    # Paginación
    paginator = Paginator(productos, 12)  # 12 productos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener todas las categorías y marcas para los filtros
    categorias = Categoria.objects.all()
    marcas = Marca.objects.all()
    
    context = {
        'productos': page_obj,
        'categorias': categorias,
        'marcas': marcas,
        'query': query,
        'selected_categoria': categoria_id,
        'selected_marca': marca_id,
    }
    return render(request, 'productos_list.html', context)  # ← CORREGIDO