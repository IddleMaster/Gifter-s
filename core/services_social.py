from django.db.models import Q
from core.models import (
    User, Seguidor, SolicitudAmistad,
    Conversacion, ParticipanteConversacion,
)

def amigos_qs(user):
    """
    Amigos = follow mutuo (yo sigo a la otra persona y la otra me sigue).
    Ojo con los related_name del modelo Seguidor:
      - en el usuario 'Y', Y.seguidores => relaciones donde 'seguido=Y'
      - en el usuario 'Y', Y.siguiendo  => relaciones donde 'seguidor=Y'
    Para obtener 'Y' amigos de 'user', pedimos:
      (a) Y.seguidores__seguidor = user   -> user sigue a Y
      (b) Y.siguiendo__seguido = user     -> Y sigue a user
    """
    return (User.objects
            .filter(seguidores__seguidor=user)   
            .filter(siguiendo__seguido=user)    
            .exclude(pk=user.pk)
            .distinct())


def sugerencias_qs(user, limit=9):
    """
    Sugerencias = otros usuarios:
      - que no soy yo
      - que NO son amigos ya
      - que NO tienen solicitud pendiente conmigo (ni enviada ni recibida)
    """
    # ids de amigos actuales
    amigos_ids = amigos_qs(user).values_list('id', flat=True)

    # usuarios involucrados en solicitudes pendientes conmigo
    pendientes_pairs = (SolicitudAmistad.objects
                        .filter(Q(emisor=user) | Q(receptor=user),
                                estado=SolicitudAmistad.Estado.PENDIENTE)
                        .values_list('emisor_id', 'receptor_id'))
    excluir_ids = {user.id, *amigos_ids}
    for e_id, r_id in pendientes_pairs:
        excluir_ids.add(e_id)
        excluir_ids.add(r_id)

    return (User.objects
            .exclude(id__in=excluir_ids)
            .order_by('-id')[:limit])


def obtener_o_crear_conv_directa(user1, user2):
    """
    Devuelve la conversación DIRECTA entre user1 y user2 si existe; si no, la crea.
    Tu modelo Conversacion requiere: tipo, creador.
    El 'tipo' correcto según tu models.py es 'directa' (Conversacion.Tipo.DIRECTA).
    """
    tipo_directa = Conversacion.Tipo.DIRECTA  

    # ¿ya existe una conversación directa con ambos participantes?
    conv = (Conversacion.objects
            .filter(tipo=tipo_directa)
            .filter(participantes__usuario=user1)
            .filter(participantes__usuario=user2)
            .distinct()
            .first())
    if conv:
        return conv

    # crearla
    conv = Conversacion.objects.create(
        tipo=tipo_directa,
        creador=user1,   # puedes elegir user1 o user2 como creador
        nombre=None
    )
    ParticipanteConversacion.objects.bulk_create([
        ParticipanteConversacion(conversacion=conv, usuario=user1),
        ParticipanteConversacion(conversacion=conv, usuario=user2),
    ])
    return conv
