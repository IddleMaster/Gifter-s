from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import MinLengthValidator
import uuid
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, username, first_name, last_name, birthdate, password=None):
        if not email:
            raise ValueError('El usuario debe tener un email')
        if not username:
            raise ValueError('El usuario debe tener un username')
        if not password:
            raise ValueError('El usuario debe tener una contraseña')
        
        user = self.model(
            email=self.normalize_email(email),
            username=username,
            first_name=first_name,
            last_name=last_name,
            birthdate=birthdate
        )
        
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    
class User(AbstractBaseUser):
    email = models.EmailField(verbose_name='email', max_length=255, unique=True)
    username = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=30, verbose_name='Nombre')
    last_name = models.CharField(max_length=30, verbose_name='Apellido')
    birthdate = models.DateField(verbose_name='Fecha de nacimiento')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')
    last_login = models.DateTimeField(auto_now=True, verbose_name='Último acceso')
    is_active = models.BooleanField(default=False, verbose_name='Activo')  # Cambiado a False
    is_verified = models.BooleanField(default=False, verbose_name='Verificado')
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True)
    token_created_at = models.DateTimeField(auto_now_add=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name', 'birthdate']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def is_verification_token_expired(self):
        return (timezone.now() - self.token_created_at).days > 1  # 24 horas
    
    def generate_new_verification_token(self):
        self.verification_token = uuid.uuid4()
        self.token_created_at = timezone.now()
        self.save()
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
            