# core/services/social.py
from __future__ import annotations

from typing import Iterable, List, Set, Dict
from django.db.models import Count, QuerySet, Q
from django.contrib.auth import get_user_model
from collections import Counter
from collections import defaultdict
from core.models import Seguidor  

User = get_user_model()


def _ids(qs: Iterable[int]) -> Set[int]:
    return set(int(x) for x in qs if x is not None)

def amigos_qs(usuario: User) -> QuerySet[User]:
    if not getattr(usuario, "is_authenticated", False):
        return User.objects.none()
    sigo_ids = _ids(Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True))
    me_siguen_ids = _ids(Seguidor.objects.filter(seguido=usuario).values_list("seguidor_id", flat=True))
    mutual_ids = (sigo_ids & me_siguen_ids) - {usuario.id}
    if not mutual_ids:
        return User.objects.none()
    return User.objects.filter(id__in=mutual_ids).select_related("perfil").order_by("-id")



def sugerencias_qs(usuario: User, limit: int = 9) -> QuerySet[User]:
    if not getattr(usuario, "is_authenticated", False):
        return User.objects.none()

    sigo_ids = _ids(Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True))
    fof_ids = _ids(Seguidor.objects.filter(seguidor_id__in=list(sigo_ids)).values_list("seguido_id", flat=True))
    candidates = fof_ids - sigo_ids - {usuario.id}

    if candidates:
        qs = (User.objects.filter(id__in=list(candidates))
              .exclude(id=usuario.id).select_related("perfil").order_by("-id")[:limit])
        if qs.exists():
            return qs

    popular_ids = list(
    Seguidor.objects
    .values("seguido_id")
    .annotate(c=Count("relacion_id"))
    .order_by("-c")
    .values_list("seguido_id", flat=True)[: limit * 4]
)

    popular_ids = [uid for uid in popular_ids if uid and uid != usuario.id and uid not in sigo_ids]
    if not popular_ids:
        return User.objects.none()
    return User.objects.filter(id__in=popular_ids).select_related("perfil").order_by("-id")[:limit]


def fof_con_senales(usuario: User, limit: int = 30) -> List[Dict]:
    """
    Devuelve candidatos FoF como una lista de dicts:
    {id, username, full_name, mutual_count, mutual_names, last_login_ts}
    """
    if not getattr(usuario, "is_authenticated", False):
        return []

    # a quién sigo
    sigo_ids = _ids(Seguidor.objects.filter(seguidor=usuario).values_list("seguido_id", flat=True))
    if not sigo_ids:
        return []

    # candidatos: a quién siguen los que yo sigo
    fof_raw = list(
        Seguidor.objects.filter(seguidor_id__in=list(sigo_ids))
        .exclude(seguido_id=usuario.id)
        .values_list("seguido_id", flat=True)
    )
    if not fof_raw:
        return []

    # contar cuántos amigos en común tiene cada candidato
    counts = Counter(fof_raw)

    # excluir a quienes YA sigo
    for sid in list(counts.keys()):
        if sid in sigo_ids:
            counts.pop(sid, None)

    if not counts:
        return []

    top_ids = [uid for uid, _c in counts.most_common(limit * 3)]  # ancho para luego recortar
    users = {u.id: u for u in User.objects.filter(id__in=top_ids).only("id","nombre","apellido","nombre_usuario","last_login")}
    if not users:
        return []

    # nombres de los amigos en común (hasta 3)
    mutual_names_map: Dict[int, List[str]] = defaultdict(list)
    # trae pares (seguidor -> seguido) solo donde seguido esté en candidatos
    relaciones = Seguidor.objects.filter(
        seguidor_id__in=list(sigo_ids),
        seguido_id__in=list(users.keys())
    ).select_related("seguidor")

    # necesitamos los nombres de quienes yo sigo (amigos en común)
    seguidor_users = {
        u.id: u for u in User.objects.filter(id__in=list(sigo_ids)).only("id","nombre","apellido","nombre_usuario")
    }

    for rel in relaciones:
        cand_id = rel.seguido_id
        amigo_id = rel.seguidor_id
        amigo = seguidor_users.get(amigo_id)
        if amigo and len(mutual_names_map[cand_id]) < 3:
            nombre = f"{(amigo.nombre or '').strip()} {(amigo.apellido or '').strip()}".strip() or (amigo.nombre_usuario or "")
            mutual_names_map[cand_id].append(nombre)

    # armar salida
    out: List[Dict] = []
    for uid, cnt in counts.most_common():
        u = users.get(uid)
        if not u:
            continue
        full_name = f"{(getattr(u,'nombre','') or '').strip()} {(getattr(u,'apellido','') or '').strip()}".strip()
        out.append({
            "id": uid,
            "username": getattr(u, "nombre_usuario", str(uid)) or str(uid),
            "full_name": full_name or getattr(u, "nombre_usuario", str(uid)),
            "mutual_count": int(cnt),
            "mutual_names": mutual_names_map.get(uid, []),
            "last_login_ts": int(u.last_login.timestamp()) if getattr(u, "last_login", None) else 0,
        })

    # orden preliminar (será refinado por LLM si está activo)
    out.sort(key=lambda x: (x["mutual_count"], x["last_login_ts"]), reverse=True)
    return out[:limit]