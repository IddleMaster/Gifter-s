from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives

from django.urls import reverse


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