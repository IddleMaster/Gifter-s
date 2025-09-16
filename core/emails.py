from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

def send_verification_email(user, request):
    verification_url = f"{settings.SITE_URL}/verify-email/{user.verification_token}/"
    
    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': 'Gifter\'s'
    }
    
    html_message = render_to_string('emails/verification_email.html', context)
    plain_message = strip_tags(html_message)
    
    email = EmailMessage(
        subject='Verifica tu cuenta en Gifter\'s',
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.content_subtype = "html"
    email.send()

def send_welcome_email(user):
    context = {
        'user': user,
        'site_name': 'Gifter\'s'
    }
    
    html_message = render_to_string('emails/welcome_email.html', context)
    plain_message = strip_tags(html_message)
    
    email = EmailMessage(
        subject='¡Bienvenido a Gifter\'s!',
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.content_subtype = "html"
    email.send()