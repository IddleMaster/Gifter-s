from pathlib import Path
import os
import environ

# === Carga de base y variables ===
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables del .env ANTES DE TODO
env = environ.Env()
env.read_env(os.path.join(BASE_DIR, ".env"))

# Variables iniciales
GIPHY_API_KEY = os.getenv("GIPHY_API_KEY", "")
# ===== Meilisearch  =====
USE_MEILI = os.getenv("USE_MEILI", "false").lower() == "true"
MEILI_URL = os.getenv("MEILI_URL", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "dev_meili_key")

OLLAMA_URL = env("OLLAMA_URL", default="http://ollama:11434")
USE_GIFTER_AI = True
# IA Local (Ollama)
GIFTER_AI_MODEL = env("GIFTER_AI_MODEL", default="llama3.2:1b")
GIFTER_AI_CACHE_TTL = env.int("GIFTER_AI_CACHE_TTL", default=1800)



AUTH_USER_MODEL = "core.User"
# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '+)9=)%0hw!lc0!_cc4o(43bb-t4$vr==(@0anb-h!9#kb4!3tg'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# --- Firebase (FCM) ---




LOGGING = {
  "version": 1,
  "disable_existing_loggers": False,
  "handlers": {"console": {"class": "logging.StreamHandler"}},
  "loggers": {
    "gifters.health": {"handlers": ["console"], "level": "INFO", "propagate": False},
  },
}

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework_simplejwt',
    'django.contrib.sites',  
    'productos_app',        
    'allauth',                       
    'allauth.account',               
    'allauth.socialaccount',         
    'allauth.socialaccount.providers.google',  
    'channels',
    'rest_framework', 
    'django_bootstrap5',
    'core.apps.CoreConfig',
    

]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',                
    'allauth.account.auth_backends.AuthenticationBackend',       
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'allauth.account.middleware.AccountMiddleware',  

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                "django.template.context_processors.request",
                'core.context.navbar_notifications',
                
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'

# <-- NUEVO: ASGI + CHANNEL LAYERS
ASGI_APPLICATION = 'myproject.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Host/puerto del servicio 'redis' en docker-compose
            "hosts": [("redis", 6379)],
        },
    },
}

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DJANGO_DB_NAME', 'gifters'),
        'USER': os.environ.get('DJANGO_DB_USER', 'gifters_user'),
        'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', 'gifters_pass'),
        'HOST': os.environ.get('DJANGO_DB_HOST', 'mysql'),
        'PORT': '3306',
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Email Configurations (usar SMTP real, no consola)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'giftersg4@gmail.com'          # <-- tu Gmail
EMAIL_HOST_PASSWORD = 'lhix entt ockg lqrl'         # <-- contraseña de aplicación (no la normal)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER            # usa el mismo remitente real

# URL base para enlaces de verificación
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'es-cl'

TIME_ZONE =  "America/Santiago"   

USE_I18N = True

USE_L10N = True

USE_TZ = True



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/
# Configuración de archivos media
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Configuración de archivos static
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'core/static'),
]
##STATIC_URL = '/assets/'
##comentado hasta que se cree assest: STATICFILES_DIRS = [os.path.join(BASE_DIR, 'assets')]


LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Configuración de allauth para tu modelo personalizado
ACCOUNT_LOGIN_METHODS = ['email']
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'correo'
ACCOUNT_EMAIL_VERIFICATION = 'optional'  # cambia a 'mandatory' si quieres forzar verificación

# Adapters (los crearemos después en core/adapters.py)
ACCOUNT_ADAPTER = 'core.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'core.adapters.CustomSocialAccountAdapter'

SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True

ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/'


# Allauth – salta la pantalla intermedia
SOCIALACCOUNT_LOGIN_ON_GET = True

# Dónde cae después de login/logout (ya lo tienes, lo dejo junto)
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# (Opcional pero recomendado) Ajustes del provider Google
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["email", "profile"],
        "AUTH_PARAMS": {"prompt": "select_account"}
    }
}

ACCOUNT_ADAPTER = "core.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "core.adapters.CustomSocialAccountAdapter"
ACCOUNT_PRESERVE_USERNAME_CASING = False

# Allauth sin username
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None   
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USER_MODEL_EMAIL_FIELD = "correo"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
# Aumenta el límite a 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB en bytes
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB en bytes

# CONFIGURACIÓN PARA ENVÍO DE CORREO
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}



# === Calendarific ===
CALENDARIFIC_API_KEY = env("CALENDARIFIC_API_KEY", default="")
CALENDARIFIC_COUNTRY = env("CALENDARIFIC_COUNTRY", default="CL")

if not CALENDARIFIC_API_KEY:
    # No detiene el arranque, pero deja trazabilidad en consola
    import logging
    logging.getLogger("gifters.health").warning(
        "Calendarific: falta CALENDARIFIC_API_KEY (solo se desactivarán funciones dependientes)."
    )

# === CAPTCHA ===
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "6Lc0nhQsAAAAABpywyuPwThF-EVwREZVc-IDHkwh")

# ✅ CORRECCIÓN: Pedir la variable "RECAPTCHA_SECRET_KEY"
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "6Lc0nhQsAAAAAGpqpKihCJ-BvDPqAn4OXgntgMMI")

LOGGING_DIR = BASE_DIR / 'logs'
if not os.path.exists(LOGGING_DIR):
    os.makedirs(LOGGING_DIR)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    
    # Cómo formatear los logs
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    
    # Dónde enviar los logs (a un archivo y a la consola)
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_web_app': {
            'level': 'INFO', # Guarda INFO, WARNING, ERROR, CRITICAL
            'class': 'logging.FileHandler',
            'filename': LOGGING_DIR / 'web_app.log', # El archivo de log
            'formatter': 'verbose',
        },
    },
    
    # Qué loggers usar
    'loggers': {
        # El logger 'raíz' (captura todo)
        '': {
            'handlers': ['console', 'file_web_app'], # Envía a ambos
            'level': 'INFO',
        },
        # Silencia un poco a Django para que no llene el log
        'django': {
            'handlers': ['console', 'file_web_app'],
            'level': 'WARNING', # Solo loggea warnings y errores de Django
            'propagate': False,
        },
        # El logger de tu app (puedes loggear desde 'core' con logging.info())
        'core': {
            'handlers': ['console', 'file_web_app'],
            'level': 'INFO',
            'propagate': False,
        }
    },
}