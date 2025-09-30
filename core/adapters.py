# core/adapters.py  (recomendado este nombre)
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils.text import slugify

class CustomAccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        # No usamos username en el modelo: no hacer nada
        return

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        full_name = data.get("name") or ""
        first = data.get("first_name") or (full_name.split(" ")[0] if full_name else "")
        last = data.get("last_name") or (" ".join(full_name.split(" ")[1:]) if full_name else "")

        # Mapea al campo 'correo' de tu modelo
        user.correo = data.get("email") or getattr(user, "correo", "") or ""
        user.nombre = first
        user.apellido = last

        # Prellenar 'nombre_usuario' (tu modelo igual lo asegura en save())
        base = slugify(f"{first}{last}") or slugify((user.correo.split("@")[0] if user.correo else ""))
        user.nombre_usuario = (base or "")[:50]

        user.is_verified = True
        return user
