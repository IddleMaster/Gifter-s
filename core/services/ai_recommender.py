from typing import Iterable, List, Optional, Sequence, Dict, Any
import json
import requests
import re

from django.conf import settings
from core.models import Producto, Wishlist, ItemEnWishlist
from core.services.ollama_client import ollama_chat


# =========================================
# Configuración IA local (Ollama)
# =========================================
OLLAMA_URL = getattr(settings, "OLLAMA_URL", "http://ollama:11434")

# ✔ Modelo correcto para embeddings
EMBED_MODEL = "nomic-embed-text"

# ✔ Modelo correcto para rerank FoF
FOF_MODEL = "llama3.2:1b"


# =========================================
# Matemáticas — Similaridad coseno
# =========================================
def _norm(v: Sequence[float]) -> float:
    return sum(x * x for x in v) ** 0.5


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(a[i] * b[i] for i in range(min(len(a), len(b))))
    na, nb = _norm(a), _norm(b)
    return dot / (na * nb) if na and nb else 0.0


# =========================================
# Texto representativo del producto
# =========================================
def _product_text(p: Producto) -> str:
    marca = getattr(getattr(p, "id_marca", None), "nombre_marca", "") or ""
    cat = getattr(getattr(p, "id_categoria", None), "nombre_categoria", "") or ""
    nombre = p.nombre_producto or ""
    desc = p.descripcion or ""
    return f"{nombre}. Marca: {marca}. Categoría: {cat}. {desc}".strip()


# =========================================
# Embeddings con OLLAMA
# =========================================
def _embed_text(text: str) -> Optional[List[float]]:
    """
    Embedding REAL usando Ollama + nomic-embed-text.
    """
    if not text.strip():
        return None

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "input": text},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        
        emb = data.get("embeddings", [])
        return emb[0] if emb else None

    except Exception:
        return None


def embed_texts(texts: List[str]) -> List[List[float]]:
    vecs = []
    for t in texts:
        emb = _embed_text(t)
        vecs.append(emb or [])
    return vecs


# =========================================
# Embeddings para productos
# =========================================
def ensure_product_embeddings(productos: Iterable[Producto]) -> None:
    textos = []
    objs = []
    index_map = []

    for p in productos:
        if not p.embedding:
            txt = _product_text(p)
            textos.append(txt)
            objs.append(p)
            index_map.append(len(textos) - 1)

    if not textos:
        return

    vecs = embed_texts(textos)

    for i, prod in enumerate(objs):
        idx = index_map[i]
        if idx < len(vecs) and vecs[idx]:
            prod.embedding = vecs[idx]

    actualizar = [p for p in objs if p.embedding]
    if actualizar:
        Producto.objects.bulk_update(actualizar, ["embedding"])


# =========================================
# Perfil del usuario 
# =========================================
def _collect_user_history_products(usuario) -> List[Producto]:
    qs = ItemEnWishlist.objects.filter(
        id_wishlist__usuario=usuario
    ).select_related("id_producto")

    recibidos = [it.id_producto for it in qs.filter(fecha_comprado__isnull=False) if it.id_producto]
    if recibidos:
        return recibidos

    return [it.id_producto for it in qs.filter(fecha_comprado__isnull=True) if it.id_producto]


def build_user_profile_embedding(usuario) -> Optional[List[float]]:
    prods = _collect_user_history_products(usuario)
    if not prods:
        return None

    ensure_product_embeddings(prods)
    vecs = [p.embedding for p in prods if p.embedding]

    if not vecs:
        return None

    dim = len(vecs[0])
    mean = [0.0] * dim

    for v in vecs:
        for i in range(dim):
            mean[i] += v[i]

    n = float(len(vecs))
    return [x / n for x in mean]


# =========================================
# Rerank productos
# =========================================
def rerank_products_with_embeddings(usuario, candidatos: Iterable[Producto], top_k: int = 3):
    profile = build_user_profile_embedding(usuario)
    cand_list = list(candidatos)

    if not profile or not cand_list:
        return cand_list[:top_k]

    ensure_product_embeddings(cand_list)

    scored = []
    for p in cand_list:
        s = _cosine(profile, p.embedding) if p.embedding else 0.0
        scored.append((s, p))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:top_k]]


# =========================================
# Re-rank FoF 
# =========================================
def _clean_json(text: str) -> str:
    """
    Limpia texto antes de json.loads (Ollama a veces mete texto extra).
    """
    # Extrae SOLO contenido entre llaves {...}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else "{}"


_SYSTEM_PROMPT_FOF = (
    "Eres un re-ranker para 'Amigos que quizá conozcas'. "
    "Usa SOLO 'mutual_count' y 'last_login_ts'. "
    "Devuelve JSON con 'ranked': [{id, score, reason}] "
    "Score 0-100. Reason <= 90 chars."
)


def rerank_fof(usuario, candidatos: List[Dict[str, Any]], take: int = 20):
    if not candidatos:
        return []

    payload = {
        "user": getattr(usuario, "nombre_usuario", str(usuario.id)),
        "candidates": candidatos[:take],
    }

    try:
        respuesta_raw = ollama_chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_FOF},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            model=FOF_MODEL,
            temperature=0.1,
        )

        texto = _clean_json(respuesta_raw)
        data = json.loads(texto)
        ranked = data.get("ranked", [])

        base = {c["id"]: c for c in candidatos}
        final = []

        for r in ranked:
            cid = r.get("id")
            if cid in base:
                c = base[cid].copy()
                c["score"] = r.get("score", 0)
                c["reason"] = r.get("reason", "")
                final.append(c)

        return final

    except Exception:
    
        return sorted(
            candidatos,
            key=lambda x: (x.get("mutual_count", 0), x.get("last_login_ts", 0)),
            reverse=True,
        )
