from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from .models import BloqueoDeUsuario, User, Seguidor

@login_required
def blocked_users_list(request):
    """Vista para mostrar la lista de usuarios bloqueados."""
    blocked_users = BloqueoDeUsuario.objects.filter(blocker=request.user).select_related('blocked')
    return render(request, 'blocked_users.html', {
        'blocked_users': blocked_users
    })

@login_required
def block_user(request, user_id):
    """Vista para bloquear a un usuario."""
    user_to_block = get_object_or_404(User, id=user_id)
    
    # Verificar que no se esté bloqueando a sí mismo
    if user_to_block == request.user:
        messages.error(request, "No puedes bloquearte a ti mismo.")
        return redirect('profile', username=user_to_block.nombre_usuario)
    
    # Verificar si ya está bloqueado
    already_blocked = BloqueoDeUsuario.objects.filter(
        blocker=request.user,
        blocked=user_to_block
    ).exists()
    
    if not already_blocked:
        # Crear el bloqueo
        BloqueoDeUsuario.objects.create(
            blocker=request.user,
            blocked=user_to_block
        )
        
        # Eliminar relación de seguimiento en ambas direcciones
        Seguidor.objects.filter(
            seguidor=request.user,
            seguido=user_to_block
        ).delete()
        
        Seguidor.objects.filter(
            seguidor=user_to_block,
            seguido=request.user
        ).delete()
        
        messages.success(request, f"Has bloqueado a {user_to_block.nombre_usuario}")
    else:
        messages.info(request, f"Ya tenías bloqueado a {user_to_block.nombre_usuario}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
        
    return redirect('blocked_users_list')

@login_required
def unblock_user(request, user_id):
    """Vista para desbloquear a un usuario."""
    user_to_unblock = get_object_or_404(User, id=user_id)
    
    # Intentar eliminar el bloqueo
    deleted = BloqueoDeUsuario.objects.filter(
        blocker=request.user,
        blocked=user_to_unblock
    ).delete()[0]
    
    if deleted:
        messages.success(request, f"Has desbloqueado a {user_to_unblock.nombre_usuario}")
    else:
        messages.info(request, f"No tenías bloqueado a {user_to_unblock.nombre_usuario}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
        
    return redirect('blocked_users_list')
