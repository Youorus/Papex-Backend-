# api/utils/pdf/appointment_report.py
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_daily_appointment_report(leads):
    """
    Génère un PDF récapitulatif moderne de tous les rendez-vous du jour.
    Retourne un objet BytesIO prêt à être envoyé par e-mail.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Récapitulatif RDV du jour")

    styles = getSampleStyleSheet()
    story = []

    # Titre principal
    story.append(Paragraph("<b>📅 RAPPORT QUOTIDIEN DES RENDEZ-VOUS</b>", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(datetime.now().strftime("Date du rapport : %d/%m/%Y"), styles["Normal"]))
    story.append(Spacer(1, 20))

    # Nombre total
    total = len(leads)
    story.append(Paragraph(f"<b>Total des rendez-vous :</b> {total}", styles["Heading3"]))
    story.append(Spacer(1, 12))

    # Tableau des rendez-vous
    data = [["Nom complet", "Téléphone", "Email", "Heure RDV", "Statut"]]

    for lead in leads:
        data.append([
            f"{lead.first_name} {lead.last_name}",
            lead.phone or "-",
            lead.email or "-",
            lead.appointment_date.strftime("%H:%M") if lead.appointment_date else "-",
            lead.status.label if lead.status else "-",
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F9FAFB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))

    story.append(table)
    story.append(Spacer(1, 24))
    story.append(Paragraph("— Généré automatiquement par TDS France —", styles["Italic"]))

    doc.build(story)
    buffer.seek(0)
    return buffer