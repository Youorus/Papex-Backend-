"""
Rapport d'analyse commerciale — Leads, Contrats, Paiements
===========================================================
Ce script se connecte à la base de données de production et génère
un PDF de reporting complet, lisible par toute personne sachant lire
des chiffres, sans connaissance technique requise.

Usage :
    python lead_analytics_report.py

Dépendances :
    pip install reportlab django
"""

import os
import django
from datetime import datetime, date
from decimal import Decimal

# ─── Initialisation Django ────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.db.models import Count, Q, Sum, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone

from api.leads.models import Lead
from api.leads.constants import (
    RDV_CONFIRME, RDV_A_CONFIRMER, RDV_PLANIFIE,
    A_RAPPELER, ABSENT, PRESENT,
    RDV_PRESENTIEL, RDV_TELEPHONE, RDV_VISIO_CONFERENCE,
)

try:
    from api.contracts.models import Contract
    HAS_CONTRACTS = True
except ImportError:
    HAS_CONTRACTS = False

try:
    from api.payments.models import PaymentReceipt
    HAS_PAYMENTS = True
except ImportError:
    HAS_PAYMENTS = False

# ─── ReportLab ────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)

# ─── Palette de couleurs ──────────────────────────────────────────────────────
BLEU_FONCE   = colors.HexColor("#1A3C5E")
BLEU_MOYEN   = colors.HexColor("#2E86C1")
BLEU_CLAIR   = colors.HexColor("#D6EAF8")
GRIS_FOND    = colors.HexColor("#F5F6FA")
GRIS_BORDURE = colors.HexColor("#BDC3C7")
GRIS_TEXTE   = colors.HexColor("#7F8C8D")
BLANC        = colors.white
VERT         = colors.HexColor("#1E8449")
ORANGE       = colors.HexColor("#E67E22")
ROUGE        = colors.HexColor("#C0392B")
JAUNE_FOND   = colors.HexColor("#FEFDE7")


# ─── Styles typographiques ────────────────────────────────────────────────────
def make_styles():
    return {
        "titre_rapport": ParagraphStyle(
            "titre_rapport", fontName="Helvetica-Bold", fontSize=24,
            textColor=BLEU_FONCE, spaceAfter=6, leading=28,
        ),
        "sous_titre": ParagraphStyle(
            "sous_titre", fontName="Helvetica", fontSize=11,
            textColor=GRIS_TEXTE, spaceAfter=20, leading=16,
        ),
        "titre_section": ParagraphStyle(
            "titre_section", fontName="Helvetica-Bold", fontSize=14,
            textColor=BLEU_FONCE, spaceBefore=20, spaceAfter=4, leading=18,
        ),
        "titre_sous_section": ParagraphStyle(
            "titre_sous_section", fontName="Helvetica-Bold", fontSize=10,
            textColor=BLEU_MOYEN, spaceBefore=14, spaceAfter=3,
        ),
        "explication": ParagraphStyle(
            "explication", fontName="Helvetica-Oblique", fontSize=8,
            textColor=GRIS_TEXTE, spaceAfter=6, leading=12,
            leftIndent=4,
        ),
        "corps": ParagraphStyle(
            "corps", fontName="Helvetica", fontSize=9,
            textColor=colors.HexColor("#2C3E50"), spaceAfter=4, leading=13,
        ),
        "gras": ParagraphStyle(
            "gras", fontName="Helvetica-Bold", fontSize=9,
            textColor=colors.HexColor("#2C3E50"),
        ),
        "note": ParagraphStyle(
            "note", fontName="Helvetica", fontSize=7.5,
            textColor=GRIS_TEXTE, leading=11,
        ),
        "kpi_valeur": ParagraphStyle(
            "kpi_valeur", fontName="Helvetica-Bold", fontSize=22,
            textColor=BLEU_FONCE, alignment=1, leading=26,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", fontName="Helvetica", fontSize=8,
            textColor=GRIS_TEXTE, alignment=1, leading=11,
        ),
        "encadre": ParagraphStyle(
            "encadre", fontName="Helvetica", fontSize=8.5,
            textColor=colors.HexColor("#2C3E50"), leading=13,
            leftIndent=6, rightIndent=6,
        ),
    }


# ─── Utilitaires ─────────────────────────────────────────────────────────────
def pct(part, total):
    """Calcule un pourcentage proprement."""
    if not total or total == 0:
        return "0 %"
    return f"{part / total * 100:.1f} %"

def fmt_euros(val):
    """Formate un montant en euros lisible."""
    if val is None:
        return "0,00 EUR"
    return f"{float(val):,.2f} EUR".replace(",", " ").replace(".", ",")

def fmt_date(d):
    """Formate une date ou datetime en français."""
    if d is None:
        return "-"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)

def bloc_kpi(styles, kpis):
    """
    Cree une rangee de cartes KPI visuelles.
    kpis = liste de (valeur_affichee, libelle_court)
    """
    n = len(kpis)
    largeur = (A4[0] - 40 * mm) / n
    ligne_valeurs = [Paragraph(str(v), styles["kpi_valeur"]) for v, _ in kpis]
    ligne_labels  = [Paragraph(l,      styles["kpi_label"])  for _, l in kpis]
    t = Table(
        [ligne_valeurs, ligne_labels],
        colWidths=[largeur] * n,
        rowHeights=[32, 20],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GRIS_FOND),
        ("BOX",           (0, 0), (-1, -1), 0.6, GRIS_BORDURE),
        ("LINEAFTER",     (0, 0), (-2, -1), 0.5, GRIS_BORDURE),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t

def tableau(styles, entetes, lignes, largeurs=None):
    """
    Tableau de donnees standard avec en-tetes bleues et lignes alternees.
    """
    en_tetes = [Paragraph(e, styles["gras"]) for e in entetes]
    data = [en_tetes] + [
        [Paragraph(str(c), styles["corps"]) for c in ligne]
        for ligne in lignes
    ]
    if largeurs is None:
        total_w = A4[0] - 40 * mm
        largeurs = [total_w / len(entetes)] * len(entetes)

    t = Table(data, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  BLEU_FONCE),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  BLANC),
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANC, GRIS_FOND]),
        ("GRID",           (0, 0), (-1, -1), 0.3, GRIS_BORDURE),
        ("LEFTPADDING",    (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 7),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t

def en_tete_section(texte, styles):
    """Titre de section avec ligne de separation."""
    return [
        Spacer(1, 4),
        Paragraph(texte, styles["titre_section"]),
        HRFlowable(width="100%", thickness=1.5, color=BLEU_MOYEN, spaceAfter=8),
    ]

def encadre_definition(texte, styles):
    """
    Petit bloc jaune pour expliquer ce que l on mesure.
    """
    data = [[Paragraph("Info : " + texte, styles["encadre"])]]
    t = Table(data, colWidths=[A4[0] - 40 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), JAUNE_FOND),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#F0E68C")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return t


# ─── Collecte des donnees ─────────────────────────────────────────────────────
def collect_data():
    d = {}
    now = timezone.now()
    d["date_rapport"] = now.strftime("%d/%m/%Y a %H:%M")

    # ── Leads ──────────────────────────────────────────────────────────────────
    tous_leads = Lead.objects.all()
    total = tous_leads.count()
    d["total_leads"] = total
    d["leads_avec_rdv"] = tous_leads.filter(appointment_date__isnull=False).count()

    premier = tous_leads.order_by("created_at").values_list("created_at", flat=True).first()
    dernier = tous_leads.order_by("-created_at").values_list("created_at", flat=True).first()
    d["premier_lead"] = fmt_date(premier)
    d["dernier_lead"] = fmt_date(dernier)

    # ── Statuts exacts (source de verite) ─────────────────────────────────────
    # PRESENT  = le client s'est presente au RDV, RDV confirme et honore
    # ABSENT   = le client ne s'est pas presente au RDV
    # RDV_CONFIRME     = RDV planifie et confirme, pas encore eu lieu
    # RDV_A_CONFIRMER  = RDV planifie, en attente de confirmation du client
    # A_RAPPELER       = prospect a rappeler, pas de RDV fixe
    # RDV_PLANIFIE     = RDV enregistre (ancien statut)

    leads_presents = tous_leads.filter(status__code=PRESENT)
    leads_absents  = tous_leads.filter(status__code=ABSENT)
    leads_confirmes = tous_leads.filter(status__code=RDV_CONFIRME)
    leads_a_confirmer = tous_leads.filter(status__code=RDV_A_CONFIRMER)
    leads_a_rappeler = tous_leads.filter(status__code=A_RAPPELER)

    d["total_presents"] = leads_presents.count()
    d["total_absents"]  = leads_absents.count()
    d["total_confirmes"] = leads_confirmes.count()
    d["total_a_confirmer"] = leads_a_confirmer.count()
    d["total_a_rappeler"] = leads_a_rappeler.count()

    # ── RDV honores : filtre sur PRESENT (source fiable) ──────────────────────
    # Presentiel : client venu physiquement + statut PRESENT
    d["presents_presentiel"] = leads_presents.filter(
        appointment_type=RDV_PRESENTIEL
    ).count()
    # Telephonique : client honore le RDV tel + statut PRESENT
    d["presents_telephone"] = leads_presents.filter(
        appointment_type=RDV_TELEPHONE
    ).count()
    # Visio : statut PRESENT + visio
    d["presents_visio"] = leads_presents.filter(
        appointment_type=RDV_VISIO_CONFERENCE
    ).count()

    # ── RDV manques : filtre sur ABSENT ───────────────────────────────────────
    d["absents_presentiel"] = leads_absents.filter(
        appointment_type=RDV_PRESENTIEL
    ).count()
    d["absents_telephone"] = leads_absents.filter(
        appointment_type=RDV_TELEPHONE
    ).count()
    d["absents_visio"] = leads_absents.filter(
        appointment_type=RDV_VISIO_CONFERENCE
    ).count()

    # ── Taux de presence par canal ────────────────────────────────────────────
    # Total des RDV passes (PRESENT + ABSENT) = RDV dont on connait l'issue
    total_rdv_presentiel_issus = d["presents_presentiel"] + d["absents_presentiel"]
    total_rdv_telephone_issus  = d["presents_telephone"]  + d["absents_telephone"]
    total_rdv_visio_issus      = d["presents_visio"]      + d["absents_visio"]

    d["taux_presence_presentiel"] = pct(d["presents_presentiel"], total_rdv_presentiel_issus)
    d["taux_presence_telephone"]  = pct(d["presents_telephone"],  total_rdv_telephone_issus)
    d["taux_presence_visio"]      = pct(d["presents_visio"],      total_rdv_visio_issus)

    d["total_rdv_presentiel_issus"] = total_rdv_presentiel_issus
    d["total_rdv_telephone_issus"]  = total_rdv_telephone_issus
    d["total_rdv_visio_issus"]      = total_rdv_visio_issus

    # ── RDV a venir : confirmes ou a confirmer (pas encore honores) ───────────
    leads_rdv_futur = tous_leads.filter(
        status__code__in=[RDV_CONFIRME, RDV_A_CONFIRMER],
        appointment_date__isnull=False,
    )
    d["rdv_futur_total"]       = leads_rdv_futur.count()
    d["rdv_futur_presentiel"]  = leads_rdv_futur.filter(appointment_type=RDV_PRESENTIEL).count()
    d["rdv_futur_telephone"]   = leads_rdv_futur.filter(appointment_type=RDV_TELEPHONE).count()
    d["rdv_futur_visio"]       = leads_rdv_futur.filter(appointment_type=RDV_VISIO_CONFERENCE).count()

    # ── Prospects sans RDV fixe ───────────────────────────────────────────────
    d["leads_sans_rdv"] = tous_leads.filter(appointment_date__isnull=True).count()
    d["leads_a_rappeler"] = d["total_a_rappeler"]

    # ── Leads urgents et prioritaires ─────────────────────────────────────────
    d["leads_urgents"] = tous_leads.filter(is_urgent=True).count()
    d["leads_chauds"]  = sum(1 for l in tous_leads if l.is_hot)

    # ── Par statut commercial (vue complete) ──────────────────────────────────
    d["par_statut"] = list(
        tous_leads.values("status__label", "status__code")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    # ── Par type de service demande ───────────────────────────────────────────
    d["par_service"] = list(
        tous_leads.values("service__label")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    # ── Par canal d acquisition ───────────────────────────────────────────────
    d["par_source"] = list(
        tous_leads.values("source")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    # ── Par departement (top 15) ──────────────────────────────────────────────
    d["par_departement"] = list(
        tous_leads.exclude(department_code="")
        .values("department_code")
        .annotate(n=Count("id"))
        .order_by("-n")[:15]
    )

    # ── Evolution mensuelle des leads entrants ────────────────────────────────
    d["evolution_mensuelle"] = list(
        tous_leads
        .annotate(mois=TruncMonth("created_at"))
        .values("mois")
        .annotate(n=Count("id"))
        .order_by("mois")
    )

    # ── Contrats ───────────────────────────────────────────────────────────────
    if HAS_CONTRACTS:
        tous_contrats = Contract.objects.all()
        total_c = tous_contrats.count()
        d["total_contrats"] = total_c

        # Taux de conversion = contrats crees / leads totaux
        d["taux_conversion"] = pct(total_c, total)

        d["contrats_signes"]     = tous_contrats.filter(is_signed=True).count()
        d["contrats_annules"]    = tous_contrats.filter(is_cancelled=True).count()
        d["contrats_rembourses"] = tous_contrats.filter(is_refunded=True).count()
        d["contrats_en_attente"] = tous_contrats.filter(
            is_signed=False, is_cancelled=False
        ).count()

        # Montants
        agg = tous_contrats.aggregate(
            total_brut=Sum("amount_due"),
            moyenne=Avg("amount_due"),
        )
        d["montant_total_brut"] = agg["total_brut"] or Decimal("0")
        d["montant_moyen"]      = agg["moyenne"]    or Decimal("0")

        # Contrats issus de leads PRESENT en presentiel vs telephone
        # (base fiable : seuls les leads dont le RDV a vraiment eu lieu)
        try:
            d["contrats_depuis_presentiel"] = tous_contrats.filter(
                client__lead__status__code=PRESENT,
                client__lead__appointment_type=RDV_PRESENTIEL,
            ).count()
            d["contrats_depuis_telephone"] = tous_contrats.filter(
                client__lead__status__code=PRESENT,
                client__lead__appointment_type=RDV_TELEPHONE,
            ).count()
            d["contrats_depuis_visio"] = tous_contrats.filter(
                client__lead__status__code=PRESENT,
                client__lead__appointment_type=RDV_VISIO_CONFERENCE,
            ).count()
        except Exception:
            d["contrats_depuis_presentiel"] = None
            d["contrats_depuis_telephone"]  = None
            d["contrats_depuis_visio"]      = None

        # Par service
        d["contrats_par_service"] = list(
            tous_contrats.values("service__label")
            .annotate(n=Count("id"), total=Sum("amount_due"))
            .order_by("-n")
        )

        # Evolution mensuelle des contrats
        d["contrats_mensuels"] = list(
            tous_contrats
            .annotate(mois=TruncMonth("created_at"))
            .values("mois")
            .annotate(n=Count("id"), total=Sum("amount_due"))
            .order_by("mois")
        )
    else:
        d["total_contrats"]  = None
        d["taux_conversion"] = "-"

    # ── Paiements ──────────────────────────────────────────────────────────────
    if HAS_PAYMENTS:
        tous_recus = PaymentReceipt.objects.all()
        d["total_recus"] = tous_recus.count()

        agg_p = tous_recus.aggregate(total=Sum("amount"))
        d["total_encaisse"] = agg_p["total"] or Decimal("0")

        d["par_mode_paiement"] = list(
            tous_recus.values("mode")
            .annotate(n=Count("id"), total=Sum("amount"))
            .order_by("-total")
        )

        d["paiements_mensuels"] = list(
            tous_recus
            .annotate(mois=TruncMonth("payment_date"))
            .values("mois")
            .annotate(n=Count("id"), total=Sum("amount"))
            .order_by("mois")
        )
    else:
        d["total_recus"]    = None
        d["total_encaisse"] = None

    return d


# ─── Construction du PDF ──────────────────────────────────────────────────────
def build_pdf(d, filename):
    styles = make_styles()
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )
    story = []
    total = d["total_leads"]

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE DE COUVERTURE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 25 * mm))
    story.append(Paragraph("Rapport d'Analyse Commerciale", styles["titre_rapport"]))
    story.append(Paragraph(
        "Genere le " + d['date_rapport'] + "  |  "
        "Donnees enregistrees du " + d['premier_lead'] + " au " + d['dernier_lead'],
        styles["sous_titre"],
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=BLEU_FONCE, spaceAfter=16))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Ce document presente une photographie complete de l'activite commerciale : "
        "le volume et la qualite des prospects recus, les rendez-vous planifies "
        "et honores, les contrats conclus et les encaissements realises. "
        "Chaque indicateur est explique pour permettre une lecture immediate, "
        "meme sans connaissance prealable du metier.",
        styles["corps"],
    ))
    story.append(Spacer(1, 10 * mm))

    # Resume en 4 chiffres cles
    kpis_couverture = [
        (total, "Prospects recus"),
        (d["leads_avec_rdv"], "Rendez-vous planifies"),
        (d["total_contrats"] if d["total_contrats"] is not None else "-", "Contrats crees"),
        (d["taux_conversion"], "Taux de conversion"),
    ]
    story.append(bloc_kpi(styles, kpis_couverture))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — LES PROSPECTS (LEADS)
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(en_tete_section("1. Les Prospects", styles))
    story.append(encadre_definition(
        "Un prospect est toute personne ayant contacte l'entreprise "
        "et dont les coordonnees ont ete enregistrees dans le systeme. "
        "Il peut s'agir d'un appel entrant, d'un formulaire web, d'un partenaire ou d'une recommandation. "
        "Le prospect devient client uniquement lorsqu'un contrat est signe.",
        styles,
    ))
    story.append(Spacer(1, 8))

    # 1.1 — Chiffres globaux
    story.append(Paragraph("1.1  Vue d'ensemble du volume de prospects", styles["titre_sous_section"]))
    story.append(Paragraph(
        "Depuis le " + d['premier_lead'] + ", l'entreprise a recu au total "
        + str(total) + " prospects.",
        styles["corps"],
    ))
    story.append(Spacer(1, 4))

    lignes_globales = [
        ["Total de prospects enregistres",
         str(total), "100 %",
         "Tous les prospects depuis l'ouverture"],
        ["Prospects dont le RDV a eu lieu (statut : Present)",
         str(d["total_presents"]), pct(d["total_presents"], total),
         "Client venu au RDV, confirme par le statut Present"],
        ["Prospects absents au RDV (statut : Absent)",
         str(d["total_absents"]), pct(d["total_absents"], total),
         "RDV planifie mais le client ne s'est pas presente"],
        ["RDV confirmes, pas encore honores",
         str(d["total_confirmes"]), pct(d["total_confirmes"], total),
         "RDV planifie et confirme, en attente de l'echeance"],
        ["RDV en attente de confirmation du client",
         str(d["total_a_confirmer"]), pct(d["total_a_confirmer"], total),
         "RDV fixe mais le client n'a pas encore confirme"],
        ["Prospects a rappeler (pas de RDV fixe)",
         str(d["total_a_rappeler"]), pct(d["total_a_rappeler"], total),
         "Aucun RDV fixe, commercial doit recontacter"],
        ["Prospects sans aucun rendez-vous",
         str(d["leads_sans_rdv"]), pct(d["leads_sans_rdv"], total),
         "Aucune date de RDV enregistree dans le systeme"],
        ["Prospects en situation urgente",
         str(d["leads_urgents"]), pct(d["leads_urgents"], total),
         "Client ayant declare une situation urgente"],
        ["Prospects prioritaires (urgents ou bloques longtemps)",
         str(d["leads_chauds"]), pct(d["leads_chauds"], total),
         "Urgents OU bloques depuis plus de 3 mois"],
    ]
    story.append(tableau(
        styles,
        ["Indicateur", "Nombre", "% du total", "Ce que cela signifie"],
        lignes_globales,
        largeurs=[78 * mm, 22 * mm, 22 * mm, 58 * mm],
    ))
    story.append(Spacer(1, 10))

    # 1.2 — Rendez-vous physiques vs telephoniques
    story.append(Paragraph("1.2  Rendez-vous honores : en personne vs par telephone", styles["titre_sous_section"]))
    story.append(encadre_definition(
        "Cette section ne compte QUE les rendez-vous qui ont reellement eu lieu, "
        "c'est-a-dire les prospects dont le statut est \"Present\". "
        "Les statut \"Absent\" (client no-show) sont affiches separement. "
        "Les RDV encore a venir (confirmes ou a confirmer) sont affiches en fin de tableau.",
        styles,
    ))
    story.append(Spacer(1, 6))

    total_rdv_issus = d["total_presents"] + d["total_absents"]

    lignes_rdv = [
        ["RDV honores en personne (client present)",
         str(d["presents_presentiel"]),
         pct(d["presents_presentiel"], d["total_presents"]),
         "Taux de presence : " + d["taux_presence_presentiel"] + " des RDV physiques passes"],
        ["RDV honores par telephone (client present)",
         str(d["presents_telephone"]),
         pct(d["presents_telephone"], d["total_presents"]),
         "Taux de presence : " + d["taux_presence_telephone"] + " des RDV tel passes"],
        ["RDV honores en visioconference (client present)",
         str(d["presents_visio"]),
         pct(d["presents_visio"], d["total_presents"]),
         "Taux de presence : " + d["taux_presence_visio"] + " des RDV visio passes"],
        ["RDV manques en personne (client absent)",
         str(d["absents_presentiel"]),
         pct(d["absents_presentiel"], d["total_absents"]),
         "Client ne s'est pas presente au RDV physique"],
        ["RDV manques par telephone (client absent)",
         str(d["absents_telephone"]),
         pct(d["absents_telephone"], d["total_absents"]),
         "Client n'a pas repondu au RDV telephonique"],
        ["RDV manques en visioconference (client absent)",
         str(d["absents_visio"]),
         pct(d["absents_visio"], d["total_absents"]),
         "Client ne s'est pas connecte au RDV visio"],
        ["RDV a venir confirmes (en personne)",
         str(d["rdv_futur_presentiel"]),
         pct(d["rdv_futur_presentiel"], d["rdv_futur_total"]),
         "RDV physique planifie, pas encore honore"],
        ["RDV a venir confirmes (telephone)",
         str(d["rdv_futur_telephone"]),
         pct(d["rdv_futur_telephone"], d["rdv_futur_total"]),
         "RDV telephonique planifie, pas encore honore"],
        ["RDV a venir confirmes (visio)",
         str(d["rdv_futur_visio"]),
         pct(d["rdv_futur_visio"], d["rdv_futur_total"]),
         "RDV visio planifie, pas encore honore"],
    ]
    story.append(tableau(
        styles,
        ["Type de rendez-vous", "Nombre", "% du groupe", "Detail"],
        lignes_rdv,
        largeurs=[76 * mm, 20 * mm, 24 * mm, 60 * mm],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Taux de presence global (tous canaux) : "
        + pct(d["total_presents"], total_rdv_issus)
        + " des rendez-vous passes ont ete honores par le client"
        + " (" + str(d["total_presents"]) + " presents sur " + str(total_rdv_issus) + " RDV passes).",
        styles["note"],
    ))
    story.append(Spacer(1, 10))

    # 1.3 — Par statut commercial
    story.append(Paragraph("1.3  Repartition par statut commercial", styles["titre_sous_section"]))
    story.append(encadre_definition(
        "Le statut indique ou en est le prospect dans le processus commercial : "
        "nouveau, rendez-vous planifie, rendez-vous confirme, contrat signe, dossier perdu, etc. "
        "C'est l'indicateur le plus direct de l'etat du pipeline commercial.",
        styles,
    ))
    story.append(Spacer(1, 6))
    if d["par_statut"]:
        lignes = [
            [s["status__label"] or "Sans statut", str(s["n"]), pct(s["n"], total)]
            for s in d["par_statut"]
        ]
        story.append(tableau(
            styles,
            ["Statut du prospect", "Nombre de prospects", "Part du total"],
            lignes,
            largeurs=[110 * mm, 40 * mm, 30 * mm],
        ))
    story.append(Spacer(1, 10))

    # 1.4 — Par type de service demande
    story.append(Paragraph("1.4  Repartition par service demande", styles["titre_sous_section"]))
    story.append(encadre_definition(
        "Lors de sa prise de contact, chaque prospect indique quel type de prestation "
        "il recherche. Cette repartition montre quels services generent le plus de demandes.",
        styles,
    ))
    story.append(Spacer(1, 6))
    if d["par_service"]:
        lignes = [
            [s["service__label"] or "Non precise", str(s["n"]), pct(s["n"], total)]
            for s in d["par_service"]
        ]
        story.append(tableau(
            styles,
            ["Service demande", "Nombre de prospects", "Part du total"],
            lignes,
            largeurs=[110 * mm, 40 * mm, 30 * mm],
        ))
    story.append(Spacer(1, 10))

    # 1.5 — Par source d acquisition
    story.append(Paragraph("1.5  D'ou viennent les prospects ? (canaux d'acquisition)", styles["titre_sous_section"]))
    story.append(encadre_definition(
        "La source indique par quel canal le prospect a connu l'entreprise : "
        "site web, recommandation, partenaire, publicite, etc. "
        "Identifier les sources les plus performantes permet d'orienter les investissements marketing.",
        styles,
    ))
    story.append(Spacer(1, 6))
    if d["par_source"]:
        lignes = [
            [s["source"] or "Non renseigne", str(s["n"]), pct(s["n"], total)]
            for s in d["par_source"]
        ]
        story.append(tableau(
            styles,
            ["Canal d'acquisition", "Nombre de prospects", "Part du total"],
            lignes,
            largeurs=[110 * mm, 40 * mm, 30 * mm],
        ))
    story.append(Spacer(1, 10))

    # 1.6 — Par departement
    story.append(Paragraph("1.6  Top 15 des departements d'origine", styles["titre_sous_section"]))
    story.append(encadre_definition(
        "Departement de residence du prospect en France metropolitaine ou DOM-TOM. "
        "Cette vue geographique permet d'identifier les zones ou la demande est la plus forte.",
        styles,
    ))
    story.append(Spacer(1, 6))
    if d["par_departement"]:
        lignes = [
            [dep["department_code"], str(dep["n"]), pct(dep["n"], total)]
            for dep in d["par_departement"]
        ]
        story.append(tableau(
            styles,
            ["Departement", "Nombre de prospects", "Part du total"],
            lignes,
            largeurs=[50 * mm, 60 * mm, 70 * mm],
        ))
    story.append(Spacer(1, 10))

    # 1.7 — Evolution mensuelle
    story.append(Paragraph("1.7  Evolution du nombre de prospects mois par mois", styles["titre_sous_section"]))
    story.append(encadre_definition(
        "Ce tableau montre combien de nouveaux prospects ont ete enregistres chaque mois. "
        "Une progression reguliere est signe d'une activite commerciale en bonne sante.",
        styles,
    ))
    story.append(Spacer(1, 6))
    if d["evolution_mensuelle"]:
        lignes = []
        for m in d["evolution_mensuelle"]:
            mois_label = m["mois"].strftime("%B %Y") if hasattr(m["mois"], "strftime") else str(m["mois"])
            lignes.append([mois_label.capitalize(), str(m["n"]), pct(m["n"], total)])
        story.append(tableau(
            styles,
            ["Mois", "Nouveaux prospects", "Part du total sur la periode"],
            lignes,
            largeurs=[70 * mm, 50 * mm, 60 * mm],
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — LES CONTRATS
    # ══════════════════════════════════════════════════════════════════════════
    if HAS_CONTRACTS and d["total_contrats"] is not None:
        story.append(PageBreak())
        story.extend(en_tete_section("2. Les Contrats", styles))
        story.append(encadre_definition(
            "Un contrat est cree lorsqu'un prospect accepte la proposition commerciale. "
            "Il formalise l'engagement du client envers l'entreprise et precise le montant du. "
            "Un contrat peut etre : en attente de signature, signe, annule ou avoir fait l'objet d'un remboursement.",
            styles,
        ))
        story.append(Spacer(1, 8))

        total_c = d["total_contrats"]

        # KPIs contrats
        kpis_contrats = [
            (total_c,                   "Contrats crees"),
            (d["contrats_signes"],       "Signes"),
            (d["contrats_en_attente"],   "En attente de signature"),
            (d["contrats_annules"],      "Annules"),
        ]
        story.append(bloc_kpi(styles, kpis_contrats))
        story.append(Spacer(1, 10))

        # 2.1 — Synthese
        story.append(Paragraph("2.1  Synthese des contrats", styles["titre_sous_section"]))
        lignes_contrats = [
            ["Contrats crees au total",
             str(total_c), "100 %",
             "Tous les contrats, quel que soit leur etat"],
            ["Contrats signes par le client",
             str(d["contrats_signes"]), pct(d["contrats_signes"], total_c),
             "Le client a signe - engagement ferme"],
            ["Contrats en attente de signature",
             str(d["contrats_en_attente"]), pct(d["contrats_en_attente"], total_c),
             "Contrat cree mais pas encore signe"],
            ["Contrats annules",
             str(d["contrats_annules"]), pct(d["contrats_annules"], total_c),
             "Contrat cree puis abandonne"],
            ["Contrats ayant fait l'objet d'un remboursement",
             str(d["contrats_rembourses"]), pct(d["contrats_rembourses"], total_c),
             "Un remboursement (total ou partiel) a ete applique"],
            ["Montant total brut de tous les contrats",
             fmt_euros(d["montant_total_brut"]), "-",
             "Somme des montants dus avant remises"],
            ["Montant moyen par contrat",
             fmt_euros(d["montant_moyen"]), "-",
             "Valeur typique d'un contrat"],
            ["Taux de conversion prospects vers contrats",
             d["taux_conversion"], "-",
             str(total) + " prospects ont genere " + str(total_c) + " contrats"],
        ]
        story.append(tableau(
            styles,
            ["Indicateur", "Valeur", "%", "Explication"],
            lignes_contrats,
            largeurs=[78 * mm, 28 * mm, 20 * mm, 54 * mm],
        ))
        story.append(Spacer(1, 10))

        # 2.2 — Conversion presentiel vs telephone
        if d["contrats_depuis_presentiel"] is not None:
            story.append(Paragraph("2.2  Conversion en contrat par canal de RDV", styles["titre_sous_section"]))
            story.append(encadre_definition(
                "Cette analyse repond a la question : quel canal de rendez-vous "
                "genere le plus de contrats signes ? "
                "La base de calcul est uniquement les prospects dont le RDV a vraiment eu lieu "
                "(statut Present), pour ne pas fausser les taux avec des RDV non honores.",
                styles,
            ))
            story.append(Spacer(1, 6))
            lignes_conv = [
                ["Contrats apres RDV en personne",
                 str(d["contrats_depuis_presentiel"]),
                 pct(d["contrats_depuis_presentiel"], d["presents_presentiel"]),
                 str(d["presents_presentiel"]) + " clients presents en personne"],
                ["Contrats apres RDV par telephone",
                 str(d["contrats_depuis_telephone"]),
                 pct(d["contrats_depuis_telephone"], d["presents_telephone"]),
                 str(d["presents_telephone"]) + " clients presents par telephone"],
                ["Contrats apres RDV en visioconference",
                 str(d["contrats_depuis_visio"]),
                 pct(d["contrats_depuis_visio"], d["presents_visio"]),
                 str(d["presents_visio"]) + " clients presents en visio"],
            ]
            story.append(tableau(
                styles,
                ["Canal de rendez-vous", "Contrats signes", "Taux de conversion", "Base de calcul"],
                lignes_conv,
                largeurs=[72 * mm, 30 * mm, 32 * mm, 46 * mm],
            ))
            story.append(Spacer(1, 10))

        # 2.3 — Par service
        story.append(Paragraph("2.3  Contrats par type de service", styles["titre_sous_section"]))
        story.append(encadre_definition(
            "Repartition des contrats selon la prestation vendue. "
            "Permet d'identifier les services les plus vendus en volume et en valeur.",
            styles,
        ))
        story.append(Spacer(1, 6))
        if d["contrats_par_service"]:
            lignes = [
                [
                    s["service__label"] or "Non precise",
                    str(s["n"]),
                    pct(s["n"], total_c),
                    fmt_euros(s["total"]),
                ]
                for s in d["contrats_par_service"]
            ]
            story.append(tableau(
                styles,
                ["Service vendu", "Nb contrats", "% du total", "Montant total du"],
                lignes,
                largeurs=[80 * mm, 28 * mm, 24 * mm, 48 * mm],
            ))
        story.append(Spacer(1, 10))

        # 2.4 — Evolution mensuelle
        story.append(Paragraph("2.4  Evolution mensuelle du nombre de contrats", styles["titre_sous_section"]))
        story.append(encadre_definition(
            "Ce tableau montre la progression des ventes mois par mois, "
            "en nombre de contrats crees et en montant total facture.",
            styles,
        ))
        story.append(Spacer(1, 6))
        if d["contrats_mensuels"]:
            lignes = []
            for m in d["contrats_mensuels"]:
                mois_label = m["mois"].strftime("%B %Y") if hasattr(m["mois"], "strftime") else str(m["mois"])
                lignes.append([
                    mois_label.capitalize(),
                    str(m["n"]),
                    fmt_euros(m["total"]),
                    pct(m["n"], total_c),
                ])
            story.append(tableau(
                styles,
                ["Mois", "Contrats crees", "Montant total facture", "% du total"],
                lignes,
                largeurs=[60 * mm, 36 * mm, 50 * mm, 34 * mm],
            ))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — LES PAIEMENTS
    # ══════════════════════════════════════════════════════════════════════════
    if HAS_PAYMENTS and d["total_recus"] is not None:
        story.append(PageBreak())
        story.extend(en_tete_section("3. Les Paiements et Encaissements", styles))
        story.append(encadre_definition(
            "Un paiement (ou recu) est enregistre chaque fois qu'un client regle tout ou partie "
            "du montant de son contrat. Un meme contrat peut donner lieu a plusieurs paiements "
            "si le client regle en plusieurs fois. "
            "Cette section montre combien d'argent a reellement ete encaisse.",
            styles,
        ))
        story.append(Spacer(1, 8))

        kpis_paiements = [
            (d["total_recus"],              "Paiements enregistres"),
            (fmt_euros(d["total_encaisse"]), "Total encaisse"),
        ]
        story.append(bloc_kpi(styles, kpis_paiements))
        story.append(Spacer(1, 10))

        # 3.1 — Par mode de paiement
        story.append(Paragraph("3.1  Repartition par mode de reglement", styles["titre_sous_section"]))
        story.append(encadre_definition(
            "Indique comment les clients paient : carte bancaire, virement, especes, cheque, etc. "
            "Utile pour evaluer les preferences des clients et anticiper les delais d'encaissement.",
            styles,
        ))
        story.append(Spacer(1, 6))
        if d["par_mode_paiement"]:
            lignes = [
                [
                    m["mode"] or "Non precise",
                    str(m["n"]),
                    fmt_euros(m["total"]),
                    pct(m["n"], d["total_recus"]),
                    pct(float(m["total"] or 0), float(d["total_encaisse"] or 1)),
                ]
                for m in d["par_mode_paiement"]
            ]
            story.append(tableau(
                styles,
                ["Mode de paiement", "Nb transactions", "Montant encaisse", "% en volume", "% en valeur"],
                lignes,
                largeurs=[50 * mm, 30 * mm, 40 * mm, 25 * mm, 35 * mm],
            ))
        story.append(Spacer(1, 10))

        # 3.2 — Evolution mensuelle
        story.append(Paragraph("3.2  Evolution mensuelle des encaissements", styles["titre_sous_section"]))
        story.append(encadre_definition(
            "Ce tableau montre, mois par mois, combien de paiements ont ete recus "
            "et quel montant total a ete encaisse. "
            "C'est l'indicateur le plus proche de la tresorerie reelle de l'entreprise.",
            styles,
        ))
        story.append(Spacer(1, 6))
        if d["paiements_mensuels"]:
            lignes = []
            for m in d["paiements_mensuels"]:
                mois_label = m["mois"].strftime("%B %Y") if hasattr(m["mois"], "strftime") else str(m["mois"])
                lignes.append([
                    mois_label.capitalize(),
                    str(m["n"]),
                    fmt_euros(m["total"]),
                ])
            story.append(tableau(
                styles,
                ["Mois", "Nombre de paiements recus", "Montant total encaisse"],
                lignes,
                largeurs=[60 * mm, 60 * mm, 60 * mm],
            ))

    # ══════════════════════════════════════════════════════════════════════════
    # PIED DE PAGE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_BORDURE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Rapport genere automatiquement le " + d['date_rapport'] + ". "
        "Toutes les donnees sont extraites en temps reel depuis la base de production. "
        "Aucune donnee n'a ete modifiee ou estimee.",
        styles["note"],
    ))

    doc.build(story)


# ─── Point d'entree ───────────────────────────────────────────────────────────
def run():
    today = date.today().strftime("%Y-%m-%d")
    filename = f"rapport_commercial_{today}.pdf"

    print("Collecte des donnees en base...")
    d = collect_data()
    print(f"    {d['total_leads']} prospects trouves")

    print("Generation du PDF...")
    build_pdf(d, filename)
    print(f"    PDF genere : {filename}")

    print("\n── Resume console ──────────────────────────────────────────")
    print(f"  Prospects total              : {d['total_leads']}")
    print(f"  Presents (RDV honore)        : {d['total_presents']}  ({pct(d['total_presents'], d['total_leads'])})")
    print(f"    dont en personne           : {d['presents_presentiel']}")
    print(f"    dont par telephone         : {d['presents_telephone']}")
    print(f"    dont en visio              : {d['presents_visio']}")
    print(f"  Absents (no-show)            : {d['total_absents']}  ({pct(d['total_absents'], d['total_leads'])})")
    print(f"  RDV confirmes a venir        : {d['rdv_futur_total']}")
    print(f"  RDV en attente confirmation  : {d['total_a_confirmer']}")
    print(f"  Prospects a rappeler         : {d['total_a_rappeler']}")
    print(f"  Prospects urgents            : {d['leads_urgents']}")
    print(f"  Prospects prioritaires       : {d['leads_chauds']}")
    if d["total_contrats"] is not None:
        print(f"  Contrats crees               : {d['total_contrats']}")
        print(f"  Contrats signes              : {d['contrats_signes']}")
        print(f"  Taux de conversion           : {d['taux_conversion']}")
        print(f"  Montant total brut           : {fmt_euros(d['montant_total_brut'])}")
    if d["total_encaisse"] is not None:
        print(f"  Total encaisse               : {fmt_euros(d['total_encaisse'])}")
    print("────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    run()