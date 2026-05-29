from django.core.management.base import BaseCommand
from api.leads_event_type.models import LeadEventType

class Command(BaseCommand):
    help = "Initialise les types d'événements système pour l'audit trail."

    def handle(self, *args, **options):
        event_types = [
            ("LEAD_CREATED", "Lead créé", "Le lead a été créé dans le système."),
            ("LEAD_UPDATED", "Lead mis à jour", "Les informations du lead ont été modifiées."),
            ("CLIENT_CREATED", "Dossier client créé", "Le dossier détaillé du client a été initialisé."),
            ("CLIENT_UPDATED", "Dossier client mis à jour", "Les informations du dossier client ont été modifiées."),
            ("COMMENT_ADDED", "Commentaire ajouté", "Un nouveau commentaire a été posté."),
            ("COMMENT_UPDATED", "Commentaire modifié", "Un commentaire existant a été édité."),
            ("CONTRACT_GENERATED", "Contrat généré", "Un nouveau contrat a été généré."),
            ("CONTRACT_UPDATED", "Contrat mis à jour", "Le contrat a subi une modification."),
            ("CONTRACT_SIGNED", "Contrat signé", "Le client a signé le contrat."),
            ("PAYMENT_RECEIVED", "Paiement reçu", "Un nouveau paiement a été enregistré."),
            ("PAYMENT_UPDATED", "Paiement mis à jour", "Un reçu de paiement a été modifié."),
            ("TASK_CREATED", "Tâche créée", "Une nouvelle tâche a été assignée."),
            ("TASK_UPDATED", "Tâche mise à jour", "Le statut ou les détails d'une tâche ont changé."),
            ("TASK_COMPLETED", "Tâche terminée", "La tâche a été marquée comme complétée."),
            ("LEAD_DELETED", "Lead supprimé", "Le lead a été supprimé du système."),
            ("CLIENT_DELETED", "Dossier client supprimé", "Le dossier client a été supprimé."),
            ("COMMENT_DELETED", "Commentaire supprimé", "Un commentaire a été supprimé."),
            ("CONTRACT_DELETED", "Contrat supprimé", "Un contrat a été supprimé."),
            ("PAYMENT_DELETED", "Paiement supprimé", "Un reçu de paiement a été supprimé."),
            ("TASK_DELETED", "Tâche supprimée", "Une tâche a été supprimée."),
        ]

        for code, label, description in event_types:
            obj, created = LeadEventType.objects.update_or_create(
                code=code,
                defaults={
                    "label": label,
                    "description": description,
                    "is_system": True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Créé: {code}"))
            else:
                self.stdout.write(f"Existant: {code}")
