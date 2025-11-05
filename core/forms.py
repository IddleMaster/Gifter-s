from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from .models import User, Perfil, PreferenciasUsuario, Evento
from .models import Post
from datetime import date
import re
from django.utils.text import slugify
from .models import ResenaSitio


def validate_image_size(file):
    """
    Valida que el tamaño del archivo no exceda los 10 MB.
    """
    max_size_mb = 10
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'El tamaño de la imagen no puede ser mayor a {max_size_mb} MB.')

def _normalize_username(raw: str, max_len: int = 50) -> str:
    return (slugify(raw or "") or "user")[:max_len]

def _suggest_username(base: str, max_len: int = 50) -> str:
    base = _normalize_username(base, max_len)
    if not User.objects.filter(nombre_usuario__iexact=base).exists():
        return base
    i = 1
    while True:
        candidate = f"{base[:max_len - (len(str(i)) + 1)]}-{i}"
        if not User.objects.filter(nombre_usuario__iexact=candidate).exists():
            return candidate
        i += 1

class LoginForm(forms.Form):
    correo = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "tu.email@ejemplo.com",
            "autocomplete": "email",
        })
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Ingresa tu contraseña",
            "autocomplete": "current-password",
        }),
        min_length=8,
        help_text="Mínimo 8 caracteres"
    )
    remember_me = forms.BooleanField(
        required=False,
        label="Recordarme"
    )
    
class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Crea una contraseña segura (mínimo 8 caracteres)',
            'id': 'password-field'
        }),
        min_length=8,
        validators=[MinLengthValidator(8)],
        help_text="La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número"
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu contraseña',
            'id': 'confirm-password-field'
        })
    )
    
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'Debes aceptar los términos y condiciones'}
    )
    
    class Meta:
        model = User
        fields = ['nombre', 'apellido', 'nombre_usuario', 'correo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tu nombre'
            }),
            'apellido': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tu apellido'
            }),
            'nombre_usuario': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Elige un nombre de usuario único'
            }),
            'correo': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'tu.email@ejemplo.com'
            }),
        }
        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'nombre_usuario': 'Nombre de usuario',
            'correo': 'Correo electrónico'
        }
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError("La contraseña es obligatoria")
        
        # Validar fortaleza de la contraseña
        if len(password) < 8:
            raise ValidationError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("La contraseña debe contener al menos una letra mayúscula")
        if not re.search(r'[a-z]', password):
            raise ValidationError("La contraseña debe contener al menos una letra minúscula")
        if not re.search(r'[0-9]', password):
            raise ValidationError("La contraseña debe contener al menos un número")
        
        return password
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Las contraseñas no coinciden")
        
        return cleaned_data
    
    def clean_correo(self):
        correo = self.cleaned_data.get('correo')
        if User.objects.filter(correo=correo).exists():
            raise ValidationError("Este correo ya está registrado")
        return correo
    
def clean_nombre_usuario(self):
    raw = self.cleaned_data.get('nombre_usuario', '')
    normalized = _normalize_username(raw)
    # excluye coincidencias case-insensitive
    if User.objects.filter(nombre_usuario__iexact=normalized).exists():
        suggestion = _suggest_username(normalized)
        raise ValidationError(f"Este nombre de usuario ya existe. Prueba con “{suggestion}”.")
    return normalized
    
    #formulario de feed
# Modifica tu PostForm de esta manera:
class PostForm(forms.ModelForm):
    contenido = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': '¿Qué estás pensando?',
            'class': 'form-control',
            'rows': 3
        }),
        label="",
        required=False
    )

    imagen = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control'
        }),
        validators=[validate_image_size]
    )

    # ✅ nuevo: campo invisible para el GIF seleccionado
    gif_url = forms.URLField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Post
        fields = ['contenido', 'imagen', 'gif_url']

    def clean(self):
        cleaned_data = super().clean()
        contenido = cleaned_data.get('contenido')
        imagen = cleaned_data.get('imagen')
        gif_url = cleaned_data.get('gif_url')

        # Evita post vacíos
        if not contenido and not imagen and not gif_url:
            raise ValidationError("Debes escribir algo, subir una imagen o elegir un GIF para publicar.")

        # Evita imagen + gif simultáneos
        if imagen and gif_url:
            raise ValidationError("No puedes subir una imagen y un GIF al mismo tiempo.")

        return cleaned_data

class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['bio', 'profile_picture', 'birth_date']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Cuéntanos algo sobre ti...'
            }),
            'birth_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': date.today().isoformat()  # ← evita elegir fechas futuras en el navegador
            }),
        }
        labels = {
            'bio': 'Biografía',
            'profile_picture': 'Foto de perfil',
            'birth_date': 'Fecha de nacimiento',
        }
        error_messages = {
            'birth_date': {
                'invalid': 'Introduce una fecha válida (formato: AAAA-MM-DD).',
            },
        }

    def clean_birth_date(self):
        d = self.cleaned_data.get('birth_date')
        if d and d > date.today():
            raise ValidationError('')
        return d

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["nombre", "apellido", "nombre_usuario"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "apellido": forms.TextInput(attrs={"class": "form-control"}),
            "nombre_usuario": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
        }
        labels = {
            "nombre": "Nombre",
            "apellido": "Apellido",
            "nombre_usuario": "Nombre de usuario",
        }

    def clean_nombre_usuario(self):
        raw = self.cleaned_data.get("nombre_usuario", "")
        normalized = _normalize_username(raw)
        qs = User.objects.filter(nombre_usuario__iexact=normalized)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            suggestion = _suggest_username(normalized)
            raise ValidationError(f"Este nombre de usuario ya está en uso. Prueba con “{suggestion}”.")
        return normalized


# core/forms.py
class PreferenciasUsuarioForm(forms.ModelForm):
    class Meta:
        model = PreferenciasUsuario
        fields = [
            'email_on_new_follower',
            'email_on_event_invite',
            'email_on_birthday_reminder',
            'accepts_marketing_emails',
            'allow_push_web',            # <- NUEVO
        ]
        labels = {
            'email_on_new_follower': 'Email por nuevo seguidor',
            'email_on_event_invite': 'Email por invitación a evento',
            'email_on_birthday_reminder': 'Recordatorio de cumpleaños',
            'accepts_marketing_emails': 'Acepta correos de marketing',
            'allow_push_web': 'Recibir notificaciones push en este navegador',  # <- NUEVO
        }
        widgets = {
            'email_on_new_follower': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_event_invite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_birthday_reminder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accepts_marketing_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_push_web': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'allowPushWeb'}),  # <- NUEVO
        }

        

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ["titulo", "fecha_evento", "descripcion"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class":"form-control", "placeholder":"Mi cumpleaños"}),
            "fecha_evento": forms.DateInput(attrs={"type":"date", "class":"form-control"}),
            "descripcion": forms.Textarea(attrs={"class":"form-control", "rows":2, "placeholder":"(opcional)"}),
        }

def validate_image_size(file):
    """
    Valida que el tamaño del archivo no exceda los 10 MB.
    """
    max_size_mb = 10
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'El tamaño de la imagen no puede ser mayor a {max_size_mb} MB.')


################################################################
################################################################
################################################################

class ResenaSitioForm(forms.ModelForm):
    class Meta:
        model = ResenaSitio
        fields = ("calificacion", "comentario")
        labels = {
            "calificacion": "Calificación",
            "comentario": "Comentario",
        }
        help_texts = {
            "calificacion": "Del 1 al 5.",
            "comentario": "Opcional. Cuéntanos tu experiencia en la página.",
        }
        widgets = {
            "calificacion": forms.NumberInput(attrs={
                "min": 1,
                "max": 5,
                "value": 5,
                "class": "form-control",
                "style": "max-width:120px;",
                "aria-label": "Calificación de 1 a 5",
            }),
            "comentario": forms.Textarea(attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "¿Qué te pareció la página? (opcional)",
            }),
        }
        error_messages = {
            "calificacion": {
                "required": "Indica una calificación de 1 a 5.",
                "invalid": "La calificación debe ser un número entre 1 y 5.",
            },
            "comentario": {
                "max_length": "Tu comentario es demasiado largo.",
            },
        }

    def clean_comentario(self):
        """Normaliza espacios; el comentario es opcional."""
        comentario = (self.cleaned_data.get("comentario") or "").strip()
        return comentario

class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    subject = forms.CharField(max_length=100, required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
