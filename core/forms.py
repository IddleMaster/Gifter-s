from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from .models import User
from datetime import date
import re

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
        fields = ['first_name', 'last_name', 'username', 'email', 'birthdate']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tu nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tu apellido'
            }),
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Elige un nombre de usuario único'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'tu.email@ejemplo.com'
            }),
            'birthdate': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'username': 'Nombre de usuario',
            'email': 'Correo electrónico',
            'birthdate': 'Fecha de nacimiento'
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
        
        # Validar edad mínima (13 años)
        birthdate = cleaned_data.get('birthdate')
        if birthdate:
            today = date.today()
            age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
            if age < 13:
                raise ValidationError("Debes tener al menos 13 años para registrarte")
        
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este email ya está registrado")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("Este nombre de usuario ya existe")
        return username