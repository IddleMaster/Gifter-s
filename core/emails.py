from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives,send_mail
from django.contrib.auth import get_user_model
from django.urls import reverse
import logging
from .models import User  


User = get_user_model()

def send_verification_email(user, request):
    verification_url = f"{settings.SITE_URL}/verify-email/{user.verification_token}/"

    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': "Gifter's",
    }

    subject = "Verifica tu cuenta en Gifter's"
    html_body = render_to_string('emails/verification_email.html', context)
    text_body = strip_tags(html_body)

    # Usa EmailMultiAlternatives para enviar texto + HTML correctamente
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,  # fallback de texto
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.correo],  # <- IMPORTANTE: tu modelo usa 'correo'
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)  # queremos que levante excepción si falla

def send_welcome_email(user):
    context = {
        'user': user,
        'site_name': "Gifter's",
    }

    subject = "¡Bienvenido a Gifter's!"
    html_body = render_to_string('emails/welcome_email.html', context)
    text_body = strip_tags(html_body)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.correo],  # <- también aquí
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)


def send_report_email(reporter, post, motivo=None, request=None):
    """Envía un email al soporte cuando un usuario reporta un post.

    reporter: instancia User que reporta
    post: instancia Post reportada
    motivo: texto opcional con la razón del reporte
    request: opcional, para generar URLs absolutas
    """
    motivo = motivo or 'No especificado'
    subject = f"[Reporte] Post #{getattr(post, 'id_post', getattr(post, 'pk', 'n/a'))} reportado"

    author = getattr(post, 'id_usuario', None)
    author_info = f"{getattr(author, 'nombre_usuario', '')} (id={getattr(author, 'id', '')})" if author else 'Desconocido'

    post_content = getattr(post, 'contenido', '') or ''
    post_excerpt = (post_content[:300] + '...') if len(post_content or '') > 300 else post_content

    post_link = None
    try:
        if request:
            # Intentamos construir una URL al feed o al post si es posible
            post_link = request.build_absolute_uri(f"/feed/#post-{getattr(post, 'id_post', getattr(post, 'pk', ''))}")
    except Exception:
        post_link = None

    body = (
        f"Reporte de publicación\n\n"
        f"Reportado por: {reporter.nombre_usuario} (id={reporter.id})\n"
        f"Email reportero: {getattr(reporter, 'correo', '')}\n"
        f"Motivo: {motivo}\n\n"
        f"Post ID: {getattr(post, 'id_post', getattr(post, 'pk', ''))}\n"
        f"Autor: {author_info}\n"
        f"Contenido (excerpt):\n{post_excerpt}\n\n"
    )
    if post_link:
        body += f"Link: {post_link}\n\n"

    recipients = ["giftersg4@gmail.com"]

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.attach_alternative(body.replace('\n', '<br/>'), "text/html")
        email.send(fail_silently=False)
    except Exception:
        # No queremos que esto rompa la UX; quien llame puede capturar la excepción
        raise
def send_temporary_password_email(user: User, temporary_password: str):
    """
    Envía el correo al usuario con su contraseña temporal y la instrucción de cambio.
    """
    subject = "Tu contraseña temporal para Gifter's"
    
    context = {
        'user': user,
        'temporary_password': temporary_password,
        'site_url': settings.SITE_URL 
    }
    
    html_message = render_to_string('emails/temporary_password_email.html', context)
    
    try:
        send_mail(
            subject=subject,
            message=f"Tu contraseña temporal es: {temporary_password}. Debes cambiarla al iniciar sesión.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.correo],
            fail_silently=False,
            html_message=html_message
        )
        logging.info(f"Contraseña temporal enviada a {user.correo}.")
    except Exception as e:
        logging.error(f"FALLO CRÍTICO al enviar temp password a {user.correo}: {e}")
        raise e
    
def send_admin_reset_notification(user_to_reset: User, temporary_password: str):
    """
    [NUEVO] Envía la contraseña temporal al correo del administrador 
    y notifica al usuario sobre el siguiente paso.
    """
    admin_email = "giftersg4@gmail.com"  # El correo de destino
    
    subject = f"⚠️ [ACCIÓN REQUERIDA] Restablecimiento de Contraseña para {user_to_reset.nombre_usuario}"
    
    context = {
        'user': user_to_reset,
        'temporary_password': temporary_password,
        'admin_email': admin_email,
        'site_url': settings.SITE_URL 
    }
    
    # Este template debe ser muy claro para el admin
    html_message = render_to_string('emails/admin_reset_notification.html', context)
    
    try:
        send_mail(
            subject=subject,
            message=f"El usuario {user_to_reset.correo} olvidó su contraseña. Contraseña Temporal: {temporary_password}. Favor contactar al usuario para proporcionarla.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False,
            html_message=html_message
        )
        logging.info(f"Notificación de contraseña temporal enviada a ADMIN para {user_to_reset.correo}.")
    except Exception as e:
        logging.error(f"FALLO CRÍTICO al enviar notificación de restablecimiento a ADMIN: {e}")
        raise e # Relanzamos el error para que la vista lo capture
    
def send_warning_email(user: User, motivo: str, admin_user: User):
    """
    Envía un correo de advertencia a un usuario de parte de un admin.
    """
    subject = "Has recibido una advertencia de moderación - Gifter's"
    
    context = {
        'user': user,
        'motivo': motivo,
        'admin_user': admin_user
    }
    
    html_message = render_to_string('emails/warning_email.html', context)
    
    try:
        send_mail(
            subject=subject,
            message='', # El mensaje de texto plano se ignora si se usa html_message
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.correo],
            fail_silently=False,
            html_message=html_message
        )
        logging.info(f"Admin '{admin_user.nombre_usuario}' envió advertencia a '{user.nombre_usuario}' por: {motivo}")
    except Exception as e:
        logging.error(f"FALLO al enviar correo de advertencia a {user.correo}: {e}")
        raise e # Relanzamos el error para que la API pueda reportarlo