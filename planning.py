from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
import calendar
from datetime import date
import ssl

# --- 1. CONFIGURATION VISUELLE ---
# URL du logo
LOGO_URL = "https://papiers-express.fr/logo.png"
LOGO_WIDTH = 2.5 * cm  # J'ai légèrement agrandi (2.5cm) pour qu'il soit visible mais discret

COLOR_ENTREPRISE = colors.HexColor("#FFF375")  # Jaune
COLOR_FORMATION = colors.HexColor("#367DA2")  # Bleu
COLOR_FERIE = colors.HexColor("#FFCCCC")  # Rouge clair
COLOR_WEEKEND = colors.HexColor("#F2F2F2")  # Gris clair
COLOR_TEXT_DARK = colors.HexColor("#333333")
COLOR_TEXT_WHITE = colors.white

# --- 2. CONFIGURATION DES DATES ---
RANGES_FORMATION = [
    (2025, 9, 22, 26), (2025, 10, 13, 17), (2025, 11, 3, 7),
    (2025, 11, 24, 28), (2025, 12, 15, 19), (2026, 1, 19, 23),
    (2026, 2, 9, 13), (2026, 3, 2, 6), (2026, 3, 23, 27),
    (2026, 4, 13, 17), (2026, 5, 4, 7), (2026, 5, 26, 29),
    (2026, 6, 15, 19), (2026, 6, 22, 26), (2026, 6, 29, 30),
    (2026, 7, 1, 3), (2026, 7, 6, 10), (2026, 9, 14, 18),
]

JOURS_FERIES = [
    (2025, 11, 1), (2025, 11, 11), (2025, 12, 25),
    (2026, 1, 1), (2026, 4, 6), (2026, 5, 1), (2026, 5, 8),
    (2026, 5, 14), (2026, 5, 25), (2026, 7, 14), (2026, 8, 15)
]

VACANCES_NOEL = [(2025, 12, 22, 31), (2026, 1, 1, 2)]


def get_day_type(d):
    if d.weekday() >= 5: return "WEEKEND"
    if (d.year, d.month, d.day) in JOURS_FERIES: return "FERIE"
    for (y, m, d1, d2) in VACANCES_NOEL:
        if d.year == y and d.month == m and d1 <= d.day <= d2: return "FERIE"
    for (y, m, d1, d2) in RANGES_FORMATION:
        if d.year == y and d.month == m and d1 <= d.day <= d2: return "FORMATION"
    return "ENTREPRISE"


# --- 3. FONCTION TECHNIQUE POUR LE LOGO ---
def dessiner_logo(c, width, height):
    """Télécharge et dessine le logo en haut à gauche"""
    try:
        # Contournement des erreurs de certificat SSL (sécurité Python)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Chargement de l'image
        import urllib.request
        with urllib.request.urlopen(LOGO_URL, context=ctx) as response:
            img_data = response.read()

        # Création de l'objet ImageReader depuis les données en mémoire
        from reportlab.lib.utils import ImageReader
        from io import BytesIO
        logo = ImageReader(BytesIO(img_data))

        # Calcul du ratio pour ne pas déformer le logo
        iw, ih = logo.getSize()
        aspect = ih / float(iw)
        logo_height = LOGO_WIDTH * aspect

        # Positionnement : X=1cm (marge gauche), Y aligné avec le titre
        # Le titre est à height - 3cm. On place le logo à sa gauche ou juste au-dessus.
        # Ici : Coin supérieur gauche
        pos_x = 1.0 * cm
        pos_y = height - 3.5 * cm

        c.drawImage(logo, pos_x, pos_y, width=LOGO_WIDTH, height=logo_height, mask='auto')
        return pos_x + LOGO_WIDTH + 1 * cm  # Retourne la position où commencer le titre

    except Exception as e:
        print(f"Erreur LOGO : {e}")
        return 3 * cm  # Position par défaut du titre si pas de logo


# --- 4. DESSIN DE LA PAGE ---
def dessiner_mois(c, annee, mois):
    width, height = landscape(A4)

    # 1. Dessiner le logo et récupérer le décalage pour le titre
    titre_x_start = dessiner_logo(c, width, height)

    # 2. Titre (décalé pour ne pas chevaucher le logo)
    mois_fr = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
               "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    titre = f"{mois_fr[mois]} {annee}"

    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(COLOR_TEXT_DARK)
    # On aligne le titre verticalement avec le logo
    c.drawString(titre_x_start, height - 3.0 * cm, titre)

    # 3. Légende
    def draw_legend(x, y, color, label):
        c.setFillColor(color)
        c.rect(x, y, 0.6 * cm, 0.6 * cm, fill=1, stroke=0)
        c.setFillColor(COLOR_TEXT_DARK)
        c.setFont("Helvetica", 10)
        c.drawString(x + 0.8 * cm, y + 0.15 * cm, label)

    draw_legend(width - 8 * cm, height - 2.5 * cm, COLOR_ENTREPRISE, "ENTREPRISE")
    draw_legend(width - 8 * cm, height - 3.2 * cm, COLOR_FORMATION, "FORMATION")

    # 4. Grille Calendrier
    grid_start_y = height - 5 * cm
    cell_w = 3.5 * cm
    cell_h = 2.5 * cm
    margin_left = (width - (7 * cell_w)) / 2

    jours = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"]
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.grey)
    for i, jour in enumerate(jours):
        c.drawCentredString(margin_left + (i * cell_w) + (cell_w / 2), grid_start_y + 0.5 * cm, jour)

    cal = calendar.monthcalendar(annee, mois)
    y = grid_start_y

    for row in cal:
        y -= cell_h
        for col, day in enumerate(row):
            x = margin_left + (col * cell_w)

            if day == 0:
                bg = colors.white
            else:
                dtype = get_day_type(date(annee, mois, day))
                if dtype == "FORMATION":
                    bg = COLOR_FORMATION
                elif dtype == "ENTREPRISE":
                    bg = COLOR_ENTREPRISE
                elif dtype == "FERIE":
                    bg = COLOR_FERIE
                else:
                    bg = COLOR_WEEKEND

            c.setFillColor(bg)
            c.setStrokeColor(colors.white)
            c.rect(x, y, cell_w, cell_h, fill=1, stroke=1)

            if day != 0:
                if bg == COLOR_FORMATION:
                    c.setFillColor(colors.white)
                else:
                    c.setFillColor(COLOR_TEXT_DARK)
                c.setFont("Helvetica-Bold", 16)
                c.drawString(x + 0.3 * cm, y + cell_h - 0.8 * cm, str(day))

                if dtype == "FERIE":
                    c.setFont("Helvetica", 8)
                    c.drawString(x + 0.3 * cm, y + 0.3 * cm, "FÉRIÉ")


# --- 5. EXÉCUTION ---
def generer_pdf_annuel(filename):
    c = canvas.Canvas(filename, pagesize=landscape(A4))

    months_to_generate = [
        (2025, 9), (2025, 10), (2025, 11), (2025, 12),
        (2026, 1), (2026, 2), (2026, 3), (2026, 4),
        (2026, 5), (2026, 6), (2026, 7), (2026, 8), (2026, 9)
    ]

    for annee, mois in months_to_generate:
        dessiner_mois(c, annee, mois)
        c.showPage()

    c.save()
    print(f"Fichier généré avec succès : {filename}")


if __name__ == "__main__":
    generer_pdf_annuel("planning_annuel_logo_fixe.pdf")