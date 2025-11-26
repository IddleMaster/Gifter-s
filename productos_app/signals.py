
from django.db.models.signals import post_save, post_delete
from django.conf import settings
from django.apps import apps
from core.search import meili

def _doc_from_producto(p):
    return {
        "id": p.id_producto,
        "nombre_producto": p.nombre_producto or "",
        "descripcion": p.descripcion or "",
        "id_categoria_id": getattr(p, "id_categoria_id", None),
        "id_marca_id": getattr(p, "id_marca_id", None),
        "precio": float(p.precio) if getattr(p, "precio", None) is not None else None,
        "activo": bool(getattr(p, "activo", True)),
    }

def _on_producto_save(sender, instance, **kwargs):
    if not getattr(settings, "USE_MEILI", False):
        return
    try:
        meili().index("products").add_documents([_doc_from_producto(instance)], primary_key="id")
    except Exception:
        pass  

def _on_producto_delete(sender, instance, **kwargs):
    if not getattr(settings, "USE_MEILI", False):
        return
    try:
        meili().index("products").delete_document(str(instance.id_producto))
    except Exception:
        pass  

def connect_signals():
    # Intentar primero en productos_app, luego en core
    Producto = None
    for app_label in ("productos_app", "core"):
        try:
            Producto = apps.get_model(app_label, "Producto")
            break
        except LookupError:
            continue

    if Producto is None:
        # No existe el modelo en ninguno de los dos → no conectamos nada
        return

    post_save.connect(
        _on_producto_save, sender=Producto,
        dispatch_uid="meili_producto_post_save"
    )
    post_delete.connect(
        _on_producto_delete, sender=Producto,
        dispatch_uid="meili_producto_post_delete"
    )
