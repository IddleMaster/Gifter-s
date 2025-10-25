# core/services/social.py
from __future__ import annotations

from typing import Iterable, List, Set
from django.db.models import Count, QuerySet
from django.contrib.auth import get_user_model

from core.models import Seguidor  # ajusta el import si tu app/model se llama distinto

User = get_user_model()


def _ids(qs: Iterable[int]) -> Set[int]:
    """Utilidad para convertir value lists a set de ids."""
    return set(int(x) for x in qs if x is not None)


def amigos_qs(usuario: User) -> QuerySet[User]:
    """
    Amigos = seguimiento MUTUO.
    Retorna un QuerySet de usuarios que sigo y que me siguen.
    """
    if not getattr(usuario, "is_authenticated", False):
        return User.objects.none()

    # ids a los que SIGO
    sigo_ids = _ids(
        Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True)
    )
    # ids que ME SIGUEN
    me_siguen_ids = _ids(
        Seguidor.objects.filter(seguido=usuario).values_list("seguidor_id", flat=True)
    )

    mutual_ids = (sigo_ids & me_siguen_ids) - {usuario.id}
    if not mutual_ids:
        return User.objects.none()

    # Trae perfil si existe para foto/nombre
    return (
        User.objects.filter(id__in=mutual_ids)
        .select_related("perfil")  # si tu modelo de perfil tiene otro nombre, cámbialo
        .order_by("-id")
    )


def sugerencias_qs(usuario: User, limit: int = 9) -> QuerySet[User]:
    """
    Sugerencias = friends-of-friends + fallback a usuarios populares.
    - Excluye al propio usuario y a quienes ya sigo (o son amigos).
    - Orden aproximado por “popularidad” si no hay señales.
    """
    if not getattr(usuario, "is_authenticated", False):
        return User.objects.none()

    # A quiénes SIGO
    sigo_ids = _ids(
        Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True)
    )

    # Friends-of-friends: a quiénes siguen los que yo sigo
    fof_ids = _ids(
        Seguidor.objects.filter(seguidor_id__in=list(sigo_ids)).values_list(
            "seguido_id", flat=True
        )
    )

    # Candidatos = FOF menos yo y menos a quienes ya sigo
    candidates = fof_ids - sigo_ids - {usuario.id}

    qs: QuerySet[User]
    if candidates:
        qs = (
            User.objects.filter(id__in=list(candidates))
            .exclude(id=usuario.id)
            .select_related("perfil")
            .order_by("-id")[:limit]
        )
        if qs.exists():
            return qs

    # Fallback: usuarios “populares” (más seguidos),
    # excluyendo a mí mismo y a quienes ya sigo.
    popular_ids = list(
        Seguidor.objects.values("seguido_id")
        .annotate(c=Count("id"))
        .order_by("-c")
        .values_list("seguido_id", flat=True)[: limit * 4]
    )
    popular_ids = [uid for uid in popular_ids if uid and uid != usuario.id and uid not in sigo_ids]

    if not popular_ids:
        return User.objects.none()

    return (
        User.objects.filter(id__in=popular_ids)
        .select_related("perfil")
        .order_by("-id")[:limit]
    )
