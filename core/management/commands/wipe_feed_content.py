from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps

# util pequeño para resolver un modelo si existe
def _pick_model(candidates):
    for label in candidates:
        try:
            return apps.get_model(label)
        except Exception:
            continue
    return None

class Command(BaseCommand):
    help = (
        "Limpia SOLO el contenido del FEED (posts, comentarios, likes, reportes) "
        "sin borrar usuarios, perfiles ni otras entidades."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra conteos, no borra.")
        parser.add_argument("--delete-files", action="store_true",
                            help="Además elimina los archivos físicos (imágenes) asociados a los posts.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        delete_files = opts["delete_files"]

        # Ajustar/añadir etiquetas si modelos están en otra app distinta a 'core'
        Post = _pick_model(["core.Post", "core.Publicacion", "core.FeedPost"])
        Comentario = _pick_model(["core.Comentario", "core.PostComentario", "core.Comment"])
        Like = _pick_model(["core.Like", "core.PostLike", "core.MeGusta"])
        Reporte = _pick_model(["core.ReportePost", "core.PostReport", "core.ReportePublicacion"])

        if not Post:
            self.stdout.write(self.style.ERROR(
                "No se encontró el modelo de Post. Ajusta las etiquetas (ej. 'tuapp.Post') en este archivo."
            ))
            return

        self.stdout.write("== Limpieza de contenido del FEED ==")
        with transaction.atomic():

            # 1) Likes
            if Like:
                n = Like.objects.count()
                self.stdout.write(f"Likes         → {n} por borrar")
                if not dry:
                    Like.objects.all().delete()

            # 2) Comentarios
            if Comentario:
                n = Comentario.objects.count()
                self.stdout.write(f"Comentarios   → {n} por borrar")
                if not dry:
                    Comentario.objects.all().delete()

            # 3) Reportes (si existen)
            if Reporte:
                n = Reporte.objects.count()
                self.stdout.write(f"Reportes      → {n} por borrar")
                if not dry:
                    Reporte.objects.all().delete()

            # 4) Posts (opcionalmente borrando archivo físico de imagen)
            qs_posts = Post.objects.all()
            n_posts = qs_posts.count()
            self.stdout.write(f"Posts         → {n_posts} por borrar")

            if not dry:
                if delete_files:
                    # intentar borrar archivos físicos antes de eliminar el registro
                    # asumiendo campos posibles: 'imagen' y 'gif_url' (gif es remoto, no se borra local)
                    for p in qs_posts.iterator():
                        img = getattr(p, "imagen", None)
                        if img and hasattr(img, "delete"):
                            try:
                                img.delete(save=False)
                            except Exception:
                                # no romper por errores de storage
                                pass
                qs_posts.delete()

            if dry:
                self.stdout.write("Dry-run: no se borró nada (solo conteos).")

        self.stdout.write(self.style.SUCCESS("✔ Feed limpiado (contenido eliminado)."))
        if delete_files and not dry:
            self.stdout.write(self.style.SUCCESS("✔ Archivos de imágenes asociados a posts también eliminados."))