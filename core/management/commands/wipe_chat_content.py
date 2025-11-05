from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps

class Command(BaseCommand):
    help = "Elimina TODAS las conversaciones (privadas, grupos, eventos) y su contenido, sin borrar usuarios ni eventos."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo muestra conteos, no borra.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        Conversacion = apps.get_model("core", "Conversacion")
        ParticipanteConversacion = apps.get_model("core", "ParticipanteConversacion")
        Mensaje = apps.get_model("core", "Mensaje")
        EntregaMensaje = apps.get_model("core", "EntregaMensaje")

        with transaction.atomic():
            # 1) Borrar entregas (FK de Mensaje)
            n_entregas = EntregaMensaje.objects.count()
            self.stdout.write(f"EntregaMensaje → {n_entregas} registros por borrar")
            if not dry:
                EntregaMensaje.objects.all().delete()

            # 2) Borrar mensajes
            n_msg = Mensaje.objects.count()
            self.stdout.write(f"Mensaje → {n_msg} registros por borrar")
            if not dry:
                Mensaje.objects.all().delete()

            # 3) Borrar participantes
            n_part = ParticipanteConversacion.objects.count()
            self.stdout.write(f"ParticipanteConversacion → {n_part} registros por borrar")
            if not dry:
                ParticipanteConversacion.objects.all().delete()

            # 4) Borrar conversaciones (chats, grupos, eventos)
            n_conv = Conversacion.objects.count()
            self.stdout.write(f"Conversacion → {n_conv} registros por borrar")
            if not dry:
                Conversacion.objects.all().delete()

            if dry:
                self.stdout.write("Dry-run: no se borró nada (solo conteos).")

        self.stdout.write(self.style.SUCCESS("✔ Todas las conversaciones y su contenido fueron eliminadas."))