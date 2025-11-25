# core/services/social.py
from __future__ import annotations

from typing import Iterable, List, Set, Dict
from django.db.models import Count, QuerySet
from django.contrib.auth import get_user_model
from collections import Counter, defaultdict
from core.models import Seguidor  

User = get_user_model()


def _ids(qs: Iterable[int]) -> Set[int]:
    return set(int(x) for x in qs if x is not None)


def amigos_qs(usuario: User) -> QuerySet[User]:
    """Amigos mutuos estándar."""
    if not getattr(usuario, "is_authenticated", False):
        return User.objects.none()

    sigo_ids = _ids(Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True))
    me_siguen_ids = _ids(Seguidor.objects.filter(seguido=usuario).values_list("seguidor_id", flat=True))

    mutual_ids = (sigo_ids & me_siguen_ids) - {usuario.id}

    if not mutual_ids:
        return User.objects.none()

    return User.objects.filter(id__in=mutual_ids).select_related("perfil").order_by("-id")


def sugerencias_qs(usuario: User, limit: int = 9) -> QuerySet[User]:
    """Usuarios populares como fallback."""
    if not getattr(usuario, "is_authenticated", False):
        return User.objects.none()

    sigo_ids = _ids(Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True))

    popular_ids = list(
        Seguidor.objects
        .values("seguido_id")
        .annotate(c=Count("relacion_id"))
        .order_by("-c")
        .values_list("seguido_id", flat=True)[: limit * 4]
    )

    popular_ids = [
        uid for uid in popular_ids
        if uid and uid != usuario.id and uid not in sigo_ids
    ]

    if not popular_ids:
        return User.objects.none()

    return User.objects.filter(id__in=popular_ids).select_related("perfil").order_by("-id")[:limit]


def fof_con_senales(usuario: User, limit: int = 30) -> List[Dict]:
    """
    Recomendaciones de amigos SOLO con base de datos (rápido).
    Friends of Friends + 3 amigos en común + ordenado por peso.
    """
    if not getattr(usuario, "is_authenticated", False):
        return []

    sigo_ids = _ids(Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True))
    if not sigo_ids:
        return []

    # IDs candidatos: gente que siguen mis seguidos
    fof_raw = list(
        Seguidor.objects.filter(seguidor_id__in=list(sigo_ids))
        .exclude(seguido_id=usuario.id)
        .values_list("seguido_id", flat=True)
    )

    if not fof_raw:
        return []

    counts = Counter(fof_raw)

    # excluir gente que ya sigo
    for sid in list(counts.keys()):
        if sid in sigo_ids:
            counts.pop(sid, None)

    if not counts:
        return []

    # tomar los top candidatos
    top_ids = [uid for uid, _ in counts.most_common(limit * 2)]

    users = {
        u.id: u for u in User.objects.filter(id__in=top_ids)
        .only("id", "nombre", "apellido", "nombre_usuario", "last_login")
        .select_related("perfil")
    }

    if not users:
        return []

    # amigos en común
    mutual_names_map = defaultdict(list)

    relaciones = Seguidor.objects.filter(
        seguidor_id__in=list(sigo_ids),
        seguido_id__in=list(users.keys())
    ).select_related("seguidor")

    seguidor_users = {
        u.id: u for u in User.objects.filter(id__in=list(sigo_ids))
        .only("id", "nombre", "apellido", "nombre_usuario")
    }

    for rel in relaciones:
        cand_id = rel.seguido_id
        amigo_id = rel.seguidor_id
        amigo = seguidor_users.get(amigo_id)

        if amigo and len(mutual_names_map[cand_id]) < 3:
            nombre = f"{(amigo.nombre or '').strip()} {(amigo.apellido or '').strip()}".strip() or amigo.nombre_usuario
            mutual_names_map[cand_id].append(nombre)

    # armar salida base (rápido)
    out = []
    for uid, cnt in counts.most_common(limit):
        u = users.get(uid)
        if not u:
            continue

        full_name = f"{(u.nombre or '').strip()} {(u.apellido or '').strip()}".strip() or u.nombre_usuario

        out.append({
            "id": uid,
            "username": u.nombre_usuario or str(uid),
            "full_name": full_name,
            "mutual_count": cnt,
            "mutual_names": mutual_names_map.get(uid, []),
            "last_login_ts": int(u.last_login.timestamp()) if u.last_login else 0,
        })

    # ordenar por cantidad de amigos en común DESC
    out.sort(key=lambda x: (x["mutual_count"], x["last_login_ts"]), reverse=True)

    return out[:limit]
