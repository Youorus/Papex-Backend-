import os
import django

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.statut_dossier.models import StatutDossier


STATUTS_DOSSIER = [
    {
        "code": "DOSSIER_RECU",
        "label": "Nous avons bien reçu votre dossier et procédons actuellement à sa vérification",
        "color": "#3b82f6",
    },
    {
        "code": "PIECES_MANQUANTES",
        "label": "Des documents complémentaires sont nécessaires pour finaliser votre dossier - merci de contacter votre juriste attitré",
        "color": "#f59e0b",
    },
    {
        "code": "DOSSIER_COMPLET",
        "label": "Votre dossier est complet et validé par nos services",
        "color": "#10b981",
    },
    {
        "code": "DOSSIER_EN_COURS",
        "label": "Votre dossier est en cours de traitement par nos services",
        "color": "#2563eb",
    },
    {
        "code": "EN_ATTENTE_INSTRUCTION_PREFECTURE",
        "label": "Votre dossier a été transmis et est actuellement en cours d’instruction par la préfecture",
        "color": "#8b5cf6",
    },
    {
        "code": "ATTESTATION_DEPOT_ENVOYEE",
        "label": "Votre attestation de dépôt vous a été transmise",
        "color": "#06b6d4",
    },
    {
        "code": "API_ENVOYEE",
        "label": "Votre attestation de prolongation d’instruction vous a été transmise",
        "color": "#0ea5e9",
    },
    {
        "code": "DOSSIER_DEPOSE_CONSULAT",
        "label": "Votre dossier a bien été déposé auprès du consulat",
        "color": "#6366f1",
    },
    {
        "code": "EN_ATTENTE_DECISION_CONSULAT",
        "label": "Votre dossier est en attente de la décision du consulat",
        "color": "#a855f7",
    },
    {
        "code": "RELANCE_PREFECTURE_EFFECTUEE",
        "label": "Une relance a été effectuée auprès de la préfecture - nous sommes dans l’attente de son retour",
        "color": "#7c3aed",
    },
    {
        "code": "PREMIERE_DEMARCHE_SUIVI",
        "label": "Une première démarche de suivi a été effectuée auprès de la préfecture",
        "color": "#4f46e5",
    },
    {
        "code": "DEUXIEME_DEMARCHE_SUIVI",
        "label": "Une deuxième démarche de suivi a été effectuée auprès de la préfecture",
        "color": "#4338ca",
    },
    {
        "code": "TROISIEME_DEMARCHE_SUIVI",
        "label": "Une troisième démarche de suivi a été effectuée auprès de la préfecture",
        "color": "#3730a3",
    },
    {
        "code": "EN_ATTENTE_REPONSE_PREFECTURE",
        "label": "Nous sommes en attente d’un retour de la préfecture concernant votre dossier",
        "color": "#8b5cf6",
    },
    {
        "code": "REQUETE_ENVOYEE_PROCUREUR",
        "label": "Votre requête a été adressée au Procureur de la République et est en cours de traitement",
        "color": "#14b8a6",
    },
    {
        "code": "DOSSIER_SUSPENDU",
        "label": "Le traitement de votre dossier est temporairement suspendu - merci de contacter votre juriste attitré",
        "color": "#ef4444",
    },
    {
        "code": "DECISION_FAVORABLE",
        "label": "Une décision favorable a été rendue concernant votre dossier",
        "color": "#22c55e",
    },
    {
        "code": "DECISION_DEFAVORABLE",
        "label": "Une décision défavorable a été rendue concernant votre dossier - merci de contacter votre juriste attitré",
        "color": "#dc2626",
    },
    {
        "code": "DOSSIER_CLOTURE",
        "label": "Le traitement de votre dossier est terminé",
        "color": "#6b7280",
    },
]


def run():
    print("🚀 Création des statuts dossier en cours...")

    created_count = 0
    updated_count = 0

    for item in STATUTS_DOSSIER:
        normalized_code = item["code"].strip().upper().replace(" ", "_")

        obj, created = StatutDossier.objects.update_or_create(
            code=normalized_code,
            defaults={
                "label": item["label"],
                "color": item["color"],
            },
        )

        if created:
            created_count += 1
            print(f"✅ Créé : {obj.label} ({obj.code})")
        else:
            updated_count += 1
            print(f"♻️ Mis à jour : {obj.label} ({obj.code})")

    print("--------------------------------------------------")
    print(f"✅ Terminé")
    print(f"🆕 Créés : {created_count}")
    print(f"🔁 Mis à jour : {updated_count}")
    print(f"📦 Total traité : {created_count + updated_count}")


if __name__ == "__main__":
    run()