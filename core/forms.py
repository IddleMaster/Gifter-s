from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from .models import User, Perfil, PreferenciasUsuario, Evento
from .models import Post
from datetime import date
import re

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
        nombre_usuario = self.cleaned_data.get('nombre_usuario')
        if User.objects.filter(nombre_usuario=nombre_usuario).exists():
            raise ValidationError("Este nombre de usuario ya existe")
        return nombre_usuario
    
    #formulario de feed
class PostForm(forms.ModelForm):
    contenido = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': '¿Qué estás pensando?',
            'class': 'form-control', # Puedes añadir clases para el estilo
            'rows': 3
        }),
        label="" # Ocultamos la etiqueta por defecto
    )

    class Meta:
        model = Post
        fields = ['contenido'] # Por ahora, solo permitimos posts de texto

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
                'class': 'form-control'
            }),
        }
        labels = {
            'bio': 'Biografía',
            'profile_picture': 'Foto de perfil',
            'birth_date': 'Fecha de nacimiento',
        }

class PreferenciasUsuarioForm(forms.ModelForm):
    class Meta:
        model = PreferenciasUsuario
        fields = [
            'email_on_new_follower',
            'email_on_event_invite',
            'email_on_birthday_reminder',
            'accepts_marketing_emails',
        ]
        labels = {
            'email_on_new_follower': 'Email por nuevo seguidor',
            'email_on_event_invite': 'Email por invitación a evento',
            'email_on_birthday_reminder': 'Recordatorio de cumpleaños',
            'accepts_marketing_emails': 'Acepta correos de marketing',
        }
        widgets = {
            'email_on_new_follower': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_event_invite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_on_birthday_reminder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accepts_marketing_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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