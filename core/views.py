from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.conf import settings
from .forms import RegisterForm
from .models import User
from .emails import send_verification_email, send_welcome_email


def home(request):
    return render(request, 'index.html')

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Enviar email de verificación
            try:
                send_verification_email(user, request)
                messages.success(request, '¡Cuenta creada! Te hemos enviado un email para verificar tu cuenta.')
            except Exception as e:
                messages.error(request, 'Error al enviar el email de verificación. Por favor contacta con soporte.')
                user.delete()  # Eliminar usuario si falla el email
                return redirect('register')
            
            return redirect('verification_sent')
            
    else:
        form = RegisterForm()
    
    return render(request, 'register.html', {'form': form})

def verification_sent_view(request):
    return render(request, 'verification_sent.html')

def verify_email_view(request, token):
    try:
        user = User.objects.get(verification_token=token)
        
        if user.is_verification_token_expired():
            messages.error(request, 'El enlace de verificación ha expirado.')
            return redirect('resend_verification')
        
        user.is_verified = True
        user.is_active = True
        user.verification_token = None
        user.save()
        
        # Enviar email de bienvenida
        send_welcome_email(user)
        
        messages.success(request, '¡Email verificado correctamente! Ya puedes iniciar sesión.')
        return redirect('login')
        
    except User.DoesNotExist:
        messages.error(request, 'El enlace de verificación no es válido.')
        return redirect('register')