# core/management/commands/meili_reindex_users.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.search import meili

INDEX = "users"

def user_doc(u):
    return {
        "id": u.id,
        "nombre": u.nombre or "",
        "apellido": u.apellido or "",
        "nombre_usuario": u.nombre_usuario or "",
        "correo": u.correo or "",
        "is_active": bool(u.is_active),
    }

class Command(BaseCommand):
    help = "Reindexa completo el índice 'users'"

    def handle(self, *args, **opts):
        client = meili()
        idx = client.index(INDEX)
        User = get_user_model()
        docs = [user_doc(u) for u in User.objects.all()]
        idx.delete_all_documents()
        if docs:
            idx.add_documents(docs, primary_key="id")
        self.stdout.write(self.style.SUCCESS(f"Reindexados {len(docs)} usuarios"))
