# core/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils.text import slugify
from django.db.models import Q
from django.template.loader import render_to_string 
# Importa tu modelo de usuario
from core.models import User


def ensure_unique_username(base: str, max_len: int = 50) -> str:
    """
    Devuelve un nombre_usuario único basado en 'base'.
    Si existe, agrega sufijos incrementales: base, base-1, base-2, ...
    """
    if not base:
        base = "user"

    base = slugify(base)[:max_len] or "user"
    # Si el base limpio ya no existe, úsalo tal cual
    if not User.objects.filter(nombre_usuario__iexact=base).exists():
        return base

    # Sino, busca un sufijo disponible
    i = 1
    while True:
        candidate = f"{base[:max_len - (len(str(i)) + 1)]}-{i}"
        if not User.objects.filter(nombre_usuario__iexact=candidate).exists():
            return candidate
        i += 1


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Para flujos de email/password (si los usas).
    """
    def render_mail(self, template_prefix, email, context):
        """
        Sobrescribe el método de renderizado para forzar el uso de 
        nuestras plantillas HTML personalizadas.
        """
        # Renderiza el asunto desde tu archivo de texto
        subject = render_to_string(f"{template_prefix}_subject.txt", context)
        subject = " ".join(subject.splitlines()).strip()

        # Deja que allauth haga el trabajo pesado de encontrar los .txt y .html del cuerpo
        message = super().render_mail(template_prefix, email, context)
        
        # Asigna nuestro asunto personalizado al correo final
        message.subject = subject

        return message
    
    def populate_username(self, request, user):
        # No usamos username estándar; allauth no debe rellenarlo.
        return

    # Opcional: si en algún flujo allauth intenta 'generar username',
    # puedes redirigirlo a nuestro campo 'nombre_usuario'.
    def generate_unique_username(self, txts, regex=None):
        base = "-".join([t for t in txts if t]) or "user"
        return ensure_unique_username(base)
    


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Para social login (Google).
    """
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        full_name = data.get("name") or ""
        first = data.get("first_name") or (full_name.split(" ")[0] if full_name else "")
        last = data.get("last_name") or (" ".join(full_name.split(" ")[1:]) if full_name else "")
        email = data.get("email") or getattr(user, "email", "") or ""

        # Mapea a tu modelo
        user.correo = email
        user.nombre = first or user.nombre
        user.apellido = last or user.apellido

        # Propuesta inicial de nombre_usuario (SIN guardar aún)
        localpart = (email.split("@")[0] if email else "")
        base = slugify(f"{first}{last}") or slugify(localpart) or "user"
        user.nombre_usuario = base[:50]

        # Marca verificado si así lo quieres
        user.is_verified = True
        return user

    def save_user(self, request, sociallogin, form=None):
        """
        Antes de guardar definitivamente, garantizamos nombre_usuario único.
        """
        user = sociallogin.user

        # Asegurar unicidad de nombre_usuario
        user.nombre_usuario = ensure_unique_username(user.nombre_usuario or "")

        # Deja que allauth guarde normalmente (crea usuario, vincula socialaccount, etc.)
        saved_user = super().save_user(request, sociallogin, form=form)
        return saved_user
