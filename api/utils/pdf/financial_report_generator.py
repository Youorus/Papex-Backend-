import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from django.utils import timezone
from api.contracts.models import Contract

def generate_payment_status_report_pdf() -> bytes:
    """
    Génère un rapport PDF listant tous les contrats avec un solde restant dû.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=1, # Center
        textColor=colors.HexColor("#002395")
    )
    
    cell_style = ParagraphStyle(
        'CustomCell',
        parent=styles['Normal'],
        fontSize=9,
        alignment=0 # Left
    )

    elements = []
    
    # 1. Titre
    today = timezone.localdate()
    months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    month_label = f"{months[today.month - 1]} {today.year}"
    elements.append(Paragraph(f"Rapport des Échéances - {month_label}", title_style))
    elements.append(Spacer(1, 10))

    # 2. Données
    # On récupère les contrats non soldés
    contracts = Contract.objects.filter(is_cancelled=False).select_related("client__lead").prefetch_related("receipts")
    
    today = timezone.localdate()
    current_month = today.month
    current_year = today.year

    data = [
        [
            Paragraph("<b>Client</b>", cell_style),
            Paragraph("<b>Service</b>", cell_style),
            Paragraph("<b>Total Dû</b>", cell_style),
            Paragraph("<b>Déjà Payé</b>", cell_style),
            Paragraph("<b>Reste</b>", cell_style),
            Paragraph("<b>Prochaine Échéance</b>", cell_style),
        ]
    ]

    total_receivable = 0
    active_count = 0

    # 🎯 Filtrage par mois en cours (uniquement ceux dont l'échéance tombe ce mois-ci)
    filtered_contracts = []
    for c in contracts:
        if c.is_fully_paid:
            continue
            
        last_receipt = c.receipts.order_by('-payment_date').first()
        if not last_receipt or not last_receipt.next_due_date:
            continue
            
        if last_receipt.next_due_date.month == current_month and last_receipt.next_due_date.year == current_year:
            filtered_contracts.append(c)

    # Tri manuel par date d'échéance
    sorted_contracts = sorted(
        filtered_contracts,
        key=lambda x: x.receipts.order_by('-payment_date').first().next_due_date
    )

    for contract in sorted_contracts:
        last_receipt = contract.receipts.order_by('-payment_date').first()
        due_date = last_receipt.next_due_date.strftime("%d/%m/%Y") if last_receipt and last_receipt.next_due_date else "Non définie"
        
        balance = contract.balance_due
        total_receivable += balance
        active_count += 1
        
        data.append([
            Paragraph(f"{contract.client.lead.first_name} {contract.client.lead.last_name}", cell_style),
            Paragraph(contract.service.label[:25], cell_style),
            Paragraph(f"{contract.real_amount:.2f} €", cell_style),
            Paragraph(f"{contract.net_paid:.2f} €", cell_style),
            Paragraph(f"<b>{balance:.2f} €</b>", cell_style),
            Paragraph(due_date, cell_style),
        ])

    # 3. Tableau
    table = Table(data, colWidths=[110, 110, 80, 80, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    # 4. Résumé
    summary_style = styles['Normal']
    elements.append(Paragraph(f"<b>Nombre de dossiers avec encours :</b> {active_count}", summary_style))
    elements.append(Paragraph(f"<b>Total global à recouvrer :</b> <font color='red'><b>{total_receivable:.2f} €</b></font>", summary_style))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
