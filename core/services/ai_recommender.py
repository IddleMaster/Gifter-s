# core/services/ai_recommender.py
from typing import Iterable, List, Optional, Sequence, Tuple
from core.models import Producto, Wishlist, ItemEnWishlist
from core.services.openai_client import get_openai_client

# Modelo de embeddings barato y efectivo
EMBED_MODEL = "text-embedding-3-small"  # 1536 dims

# ========== utilidades matemáticas (sin numpy) ==========
def _norm(v: Sequence[float]) -> float:
    s = 0.0
    for x in v:
        s += x * x
    return s ** 0.5

def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    n = min(len(a), len(b))
    for i in range(n):
        dot += a[i] * b[i]
    na, nb = _norm(a), _norm(b)
    return (dot / (na * nb)) if na and nb else 0.0

# ========== helpers de texto/embeddings ==========
def _product_text(p: Producto) -> str:
    """Texto representativo del producto para embedir."""
    marca = getattr(getattr(p, "id_marca", None), "nombre_marca", "") or ""
    cat = getattr(getattr(p, "id_categoria", None), "nombre_categoria", "") or ""
    nombre = getattr(p, "nombre_producto", "") or ""
    desc = getattr(p, "descripcion", "") or ""
    return f"{nombre}. Marca: {marca}. Categoría: {cat}. {desc}".strip()

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Devuelve embeddings para una lista de textos (mismo orden)."""
    client = get_openai_client(timeout_seconds=15)
    if not client or not texts:
        return []
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]

def ensure_product_embeddings(productos: Iterable[Producto]) -> None:
    """
    Calcula y guarda embeddings para productos que aún no lo tienen.
    Guarda en bulk para minimizar I/O.
    """
    textos: List[str] = []
    objs: List[Producto] = []
    index_map: List[int] = []

    for p in productos:
        if not p.embedding:
            txt = _product_text(p)
            if txt:
                index_map.append(len(textos))
                textos.append(txt)
                objs.append(p)

    if not textos:
        return

    vecs = embed_texts(textos)
    for i, prod in enumerate(objs):
        idx = index_map[i]
        if idx < len(vecs):
            prod.embedding = vecs[idx]

    # solo actualiza los que realmente obtuvieron embedding
    to_update = [p for p in objs if p.embedding]
    if to_update:
        Producto.objects.bulk_update(to_update, ["embedding"])

# ========== construir “perfil” del usuario ==========
def _collect_user_history_products(usuario) -> List[Producto]:
    """Prioriza recibidos; si no hay, usa wishlist viva como señales."""
    qs = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario).select_related("id_producto")
    recibidos = [it.id_producto for it in qs.filter(fecha_comprado__isnull=False) if it.id_producto]
    if recibidos:
        return recibidos
    wishlist_viva = [it.id_producto for it in qs.filter(fecha_comprado__isnull=True) if it.id_producto]
    return wishlist_viva

def build_user_profile_embedding(usuario) -> Optional[List[float]]:
    """Vector promedio (embedding) del gusto del usuario."""
    prods = _collect_user_history_products(usuario)
    if not prods:
        return None

    # Asegura que esos productos tengan embedding
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

# ========== re-rank de candidatos ==========
def rerank_products_with_embeddings(usuario, candidatos: Iterable[Producto], top_k: int = 3) -> List[Producto]:
    """
    Reordena candidatos por similitud coseno contra el perfil del usuario.
    Si no hay perfil o embeddings, devuelve los primeros top_k tal cual.
    """
    profile = build_user_profile_embedding(usuario)
    cand_list = list(candidatos)

    if not profile or not cand_list:
        return cand_list[:top_k]

    # asegúrate de que los candidatos tengan embedding
    ensure_product_embeddings(cand_list)

    scored = []
    for p in cand_list:
        if p.embedding:
            s = _cosine(profile, p.embedding)
        else:
            s = 0.0
        scored.append((s, p))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _s, p in scored[:top_k]]
