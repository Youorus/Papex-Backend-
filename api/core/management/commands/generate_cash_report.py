import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from api.payments.models import PaymentReceipt

class Command(BaseCommand):
    help = 'Generate a PDF report of all cash payments received to date.'

    def handle(self, *args, **options):
        self.stdout.write("Génération du rapport des paiements en espèces...")
        
        today = datetime.now().date()
        
        # Fetch data using the correct model
        payments = PaymentReceipt.objects.filter(
            mode='CASH',
            payment_date__date__lte=today
        ).select_related('client').order_by('payment_date')

        if not payments:
            self.stdout.write(self.style.WARNING("Aucun paiement en espèces trouvé."))
            return

        # Prepare data for the table
        data = [['Client', 'Date de paiement', 'Montant']]
        for p in payments:
            client_name = "N/A"
            if p.client:
                client_name = f"{p.client.first_name} {p.client.last_name}"
            
            data.append([
                client_name,
                p.payment_date.strftime('%d-%m-%Y'),
                f"{p.amount} €"
            ])

        # Generate PDF
        filename = f"rapport_paiements_especes_{today.strftime('%Y%m%d')}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # Add Title and Date
        title = Paragraph("Rapport des Paiements en Espèces", styles['h1'])
        report_date = Paragraph(f"Date du rapport : {today.strftime('%d-%m-%Y')}", styles['h3'])
        elements.append(title)
        elements.append(report_date)
        elements.append(Spacer(1, 12))

        # Create Table
        table = Table(data)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table.setStyle(style)

        elements.append(table)
        doc.build(elements)
        
        self.stdout.write(self.style.SUCCESS(f"Le rapport a été généré avec succès : {filename}"))
