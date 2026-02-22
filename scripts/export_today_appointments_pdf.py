import os
import django
from datetime import datetime, time

from django.utils import timezone

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle

from api.leads.models import Lead
from api.leads.constants import RDV_CONFIRME, RDV_A_CONFIRMER


def run():
    today = timezone.localdate()

    start_of_day = timezone.make_aware(datetime.combine(today, time.min))
    end_of_day = timezone.make_aware(datetime.combine(today, time.max))

    leads = (
        Lead.objects.filter(
            appointment_date__range=(start_of_day, end_of_day),
            status__code__in=[RDV_CONFIRME, RDV_A_CONFIRMER],
        )
        .select_related("status")
        .order_by("appointment_date")
    )

    filename = f"rdv_{today}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4)

    # 🎨 Styles avec police native
    title_style = ParagraphStyle(
        name="Title",
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=20,
    )

    cell_style = ParagraphStyle(
        name="Cell",
        fontName="Helvetica",
        fontSize=10,
    )

    elements = []

    elements.append(Paragraph(f"Rendez-vous du {today}", title_style))
    elements.append(Spacer(1, 12))

    data = [
        [
            Paragraph("Heure", cell_style),
            Paragraph("Lead", cell_style),
            Paragraph("Statut", cell_style),
            Paragraph("Type", cell_style),
        ]
    ]

    for lead in leads:
        hour = timezone.localtime(lead.appointment_date).strftime("%H:%M")
        name = f"{lead.first_name} {lead.last_name}"
        status = lead.status.label if lead.status else "-"
        type_display = lead.get_appointment_type_display()

        data.append([
            Paragraph(hour, cell_style),
            Paragraph(name, cell_style),
            Paragraph(status, cell_style),
            Paragraph(type_display, cell_style),
        ])

    table = Table(
        data,
        colWidths=[70, 200, 150, 100],
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)
    doc.build(elements)

    print(f"✅ PDF généré : {filename}")
    print(f"📊 {leads.count()} rendez-vous inclus")


if __name__ == "__main__":
    run()
