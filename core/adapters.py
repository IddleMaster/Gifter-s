
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils.text import slugify
from django.db.models import Q
from django.template.loader import render_to_string 
# Importa tu modelo de usuario
from core.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import logging
import re

logger = logging.getLogger(__name__)


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
    
    def set_password(self, user, password):
        """
        Sobrescribe el método de allauth para validar la contraseña
        con los validadores de Django antes de asignarla.
        """
        # Lanza ValidationError si no cumple los validadores
        try:
            validate_password(password, user=user)
        except ValidationError as e:
            # Registrar el fallo sin incluir la contraseña en texto claro
            logger.warning("Password validation failed for user id=%s: %s", getattr(user, 'pk', 'unknown'), e.messages)
            # Re-emitir para que el flujo que llamó al adaptador pueda manejarlo
            raise
        user.set_password(password)
        user.save()

    def clean_password(self, password, user=None):
        """
        Extiende la validación de contraseña de allauth/Django con las
        mismas reglas que usamos en el formulario de registro: mínimo 8
        caracteres, al menos una mayúscula, una minúscula y un número.
        """
        # Primero aplicar validadores estándar de Django (longitud, comunes, etc.)
        try:
            # DefaultAccountAdapter.clean_password llama a validate_password
            super_clean = getattr(super(), 'clean_password', None)
            if callable(super_clean):
                password = super_clean(password, user=user)
            else:
                validate_password(password, user=user)
        except ValidationError as e:
            # Traducir mensajes de los validadores de Django al español
            translated = []
            for err in getattr(e, 'error_list', []) or []:
                code = getattr(err, 'code', None)
                params = getattr(err, 'params', {}) or {}
                if code == 'password_too_short':
                    min_len = params.get('min_length') or params.get('limit_value') or 8
                    translated.append(f"La contraseña es demasiado corta. Debe tener al menos {min_len} caracteres.")
                elif code == 'password_too_common':
                    translated.append("La contraseña es demasiado común. Elige otra más segura.")
                elif code == 'password_entirely_numeric':
                    translated.append("La contraseña no puede estar formada solo por números.")
                elif code == 'password_too_similar':
                    translated.append("La contraseña es demasiado similar a tus datos personales.")
                else:
                    # Si no conocemos el código, usamos el mensaje original pero en español genérico
                    translated.append(str(err))

            if not translated:
                # Fallback simple
                translated = e.messages

            raise ValidationError(translated)

        # Validaciones adicionales (coincidentes con core/forms.RegisterForm)
        if not password:
            raise ValidationError("La contraseña es obligatoria")
        if len(password) < 8:
            raise ValidationError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Z]", password):
            raise ValidationError("La contraseña debe contener al menos una letra mayúscula")
        if not re.search(r"[a-z]", password):
            raise ValidationError("La contraseña debe contener al menos una letra minúscula")
        if not re.search(r"[0-9]", password):
            raise ValidationError("La contraseña debe contener al menos un número")

        return password
    


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
