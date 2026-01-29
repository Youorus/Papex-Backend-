import json
import calendar
from dataclasses import dataclass
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Dict, Optional, List

import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


# =========================
# CONFIG
# =========================

APP_TITLE = "Planning équipe — Calendrier PDF"
DATA_PATH = Path("planning.json")

MOIS_FR = [
    "", "JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN",
    "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"
]
JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

DAY_TYPES = ["TRAVAIL", "FORMATION", "TELETRAVAIL", "CONGE", "FERME", "WEEKEND", "FERIE"]

# Palette pro (douce)
PALETTE = {
    "TRAVAIL":     colors.HexColor("#FFF4CC"),
    "FORMATION":   colors.HexColor("#DCEAF7"),
    "TELETRAVAIL": colors.HexColor("#E6F7E8"),
    "CONGE":       colors.HexColor("#EDEDED"),
    "FERME":       colors.HexColor("#FFD6D6"),
    "WEEKEND":     colors.HexColor("#F5F5F5"),
    "FERIE":       colors.HexColor("#FFB3B3"),
    "VIDE":        colors.white,
}

LEGEND_ORDER = ["TRAVAIL", "FORMATION"]


# =========================
# JOURS FÉRIÉS FRANCE
# =========================

def paques(annee: int) -> date:
    a = annee % 19
    b = annee // 100
    c = annee % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    mois = (h + l - 7*m + 114) // 31
    jour = (h + l - 7*m + 114) % 31 + 1
    return date(annee, mois, jour)

def jours_feries_france(annee: int) -> set[date]:
    p = paques(annee)
    return {
        date(annee, 1, 1),
        p + timedelta(days=1),   # Lundi de Pâques
        date(annee, 5, 1),
        date(annee, 5, 8),
        p + timedelta(days=39),  # Ascension
        p + timedelta(days=50),  # Lundi de Pentecôte
        date(annee, 7, 14),
        date(annee, 8, 15),
        date(annee, 11, 1),
        date(annee, 11, 11),
        date(annee, 12, 25),
    }


# =========================
# DATA MODEL
# =========================

@dataclass
class MemberPlan:
    overrides: Dict[str, str]  # "YYYY-MM-DD" -> type
    # extension possible: rules, patterns, etc.

def load_data() -> dict:
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # default
    year = datetime.now().year
    return {"year": year, "members": {}}

def save_data(data: dict) -> None:
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_member(data: dict, name: str) -> MemberPlan:
    m = data["members"].get(name, {})
    return MemberPlan(overrides=m.get("overrides", {}))

def set_member(data: dict, name: str, mp: MemberPlan) -> None:
    if "members" not in data:
        data["members"] = {}
    data["members"][name] = {"overrides": mp.overrides}


# =========================
# LOGIQUE "TYPE DE JOUR"
# =========================

def base_day_type(d: date, feries: set[date], closed_weekends: bool = True) -> str:
    if d in feries:
        return "FERIE"
    if closed_weekends and d.weekday() >= 5:
        return "WEEKEND"
    return "TRAVAIL"

def resolved_day_type(d: date, mp: MemberPlan, feries: set[date], closed_weekends: bool) -> str:
    key = d.isoformat()
    if key in mp.overrides:
        return mp.overrides[key]
    return base_day_type(d, feries, closed_weekends=closed_weekends)


# =========================
# PDF RENDER
# =========================

def draw_badge(c: canvas.Canvas, x, y, w, h, label: str, fill_color):
    c.setFillColor(fill_color)
    c.setStrokeColor(colors.lightgrey)
    c.roundRect(x, y, w, h, 3, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(x + 4, y + (h - 9) / 2, label)

def draw_centered(c: canvas.Canvas, x, y, text, font="Helvetica-Bold", size=14):
    c.setFont(font, size)
    tw = stringWidth(text, font, size)
    c.drawString(x - tw / 2, y, text)

def render_member_pdf(
    out_path: str,
    year: int,
    member_name: str,
    mp: MemberPlan,
    closed_weekends: bool,
    extra_closures: Optional[set[date]] = None,
):
    extra_closures = extra_closures or set()
    feries = jours_feries_france(year)

    pagesize = landscape(A4)
    c = canvas.Canvas(out_path, pagesize=pagesize)
    W, H = pagesize

    margin = 14 * mm

    # Header style
    def header(month: int):
        c.setFillColor(colors.black)
        draw_centered(c, W/2, H - margin - 10, f"{MOIS_FR[month]} {year}", size=18)
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#333333"))
        c.drawString(margin, H - margin + 2, f" : {member_name}")

        # Legend
        x = margin
        y = H - margin - 28
        badge_h = 8 * mm
        gap = 3 * mm
        for t in LEGEND_ORDER:
            label = t.capitalize()
            bw = max(20 * mm, (stringWidth(label, "Helvetica", 9) + 10))
            draw_badge(c, x, y, bw, badge_h, label, PALETTE[t])
            x += bw + gap

    # Calendar grid metrics
    grid_top = H - margin - 45
    grid_left = margin
    grid_w = W - 2 * margin
    grid_h = H - margin - 65

    col_w = grid_w / 7

    for month in range(1, 13):
        c.setFillColor(colors.white)
        c.rect(0, 0, W, H, fill=1, stroke=0)

        header(month)

        # Day names row
        row_h_header = 10 * mm
        c.setStrokeColor(colors.lightgrey)
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica-Bold", 10)

        y = grid_top - row_h_header
        for col, name in enumerate(JOURS_FR):
            x = grid_left + col * col_w
            c.setFillColor(colors.HexColor("#FAFAFA"))
            c.rect(x, y, col_w, row_h_header, fill=1, stroke=1)
            c.setFillColor(colors.HexColor("#111111"))
            c.drawCentredString(x + col_w/2, y + 3*mm, name)

        # Weeks
        cal = calendar.monthcalendar(year, month)
        weeks = len(cal)
        row_h = (grid_h - row_h_header) / weeks

        for r, week in enumerate(cal):
            yy = y - (r + 1) * row_h
            for col, day in enumerate(week):
                xx = grid_left + col * col_w
                if day == 0:
                    c.setFillColor(PALETTE["VIDE"])
                    c.rect(xx, yy, col_w, row_h, fill=1, stroke=1)
                    continue

                d = date(year, month, day)

                # Fermetures globales (en plus des fériés)
                if d in extra_closures:
                    dtype = "FERME"
                else:
                    dtype = resolved_day_type(d, mp, feries, closed_weekends)

                c.setFillColor(PALETTE.get(dtype, colors.white))
                c.rect(xx, yy, col_w, row_h, fill=1, stroke=1)

                # day number
                c.setFillColor(colors.HexColor("#111111"))
                c.setFont("Helvetica-Bold", 11)
                c.drawString(xx + 2.5*mm, yy + row_h - 5.5*mm, str(day))

                # small label
                c.setFont("Helvetica", 8)
                c.setFillColor(colors.HexColor("#444444"))
                label = dtype.replace("_", " ").capitalize()
                c.drawString(xx + 2.5*mm, yy + 2.5*mm, label)

        # Footer
        c.setFillColor(colors.HexColor("#666666"))
        c.setFont("Helvetica", 8)
        c.drawRightString(W - margin, margin/2, f"Généré le {date.today().strftime('%d/%m/%Y')}")

        c.showPage()

    c.save()


# =========================
# UI STREAMLIT
# =========================

def parse_date_key(year: int, month: int, day: int) -> str:
    return date(year, month, day).isoformat()

def month_days(year: int, month: int) -> List[int]:
    _, last = calendar.monthrange(year, month)
    return list(range(1, last + 1))

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    data = load_data()
    year = int(data.get("year", datetime.now().year))

    left, right = st.columns([1, 2])

    with left:
        st.subheader("Paramètres")
        year = st.number_input("Année", min_value=2000, max_value=2100, value=year, step=1)
        closed_weekends = st.checkbox("Colorer le week-end automatiquement", value=True)

        st.markdown("---")
        st.subheader("Équipe")
        members = sorted(list(data.get("members", {}).keys()))

        new_member = st.text_input("Ajouter un membre")
        if st.button("➕ Ajouter", use_container_width=True):
            name = new_member.strip()
            if name:
                if name not in data["members"]:
                    data["members"][name] = {"overrides": {}}
                    data["year"] = year
                    save_data(data)
                st.rerun()

        if not members:
            st.info("Ajoute au moins un membre pour commencer.")
            return

        member_name = st.selectbox("Membre", members)
        mp = get_member(data, member_name)

        if st.button("🗑️ Réinitialiser les modifications de ce membre", use_container_width=True):
            mp.overrides = {}
            set_member(data, member_name, mp)
            data["year"] = year
            save_data(data)
            st.rerun()

    with right:
        st.subheader(f"Édition — {member_name}")
        st.caption("Choisis un mois, un type, puis clique sur les jours à modifier. Les jours fériés sont pris en compte automatiquement.")

        feries = jours_feries_france(year)

        colA, colB, colC = st.columns([1, 1, 2])
        with colA:
            month = st.selectbox("Mois", list(range(1, 13)), format_func=lambda m: MOIS_FR[m])
        with colB:
            selected_type = st.selectbox("Type à appliquer", ["FORMATION", "TELETRAVAIL", "CONGE", "TRAVAIL", "FERME"])
        with colC:
            st.write("")
            st.write("")

        # Affichage jours (grille simple cliquable)
        days = month_days(year, month)
        cols = st.columns(7)
        for i, day in enumerate(days):
            d = date(year, month, day)
            dtype = resolved_day_type(d, mp, feries, closed_weekends)
            label = f"{day}\n{dtype}"

            is_ferie = d in feries
            if is_ferie:
                label = f"{day}\nFERIE"

            btn_col = cols[i % 7]
            if btn_col.button(label, key=f"daybtn_{month}_{day}", use_container_width=True):
                key = d.isoformat()

                # On laisse le jour férié “visible” comme tel (base), mais tu peux forcer FERME/CONGE/etc si tu veux.
                mp.overrides[key] = selected_type

                set_member(data, member_name, mp)
                data["year"] = year
                save_data(data)
                st.rerun()

        st.markdown("---")
        st.subheader("Export PDF")

        out_name = st.text_input("Nom du fichier PDF", value=f"planning_{member_name}_{year}.pdf")

        if st.button("📄 Générer le PDF", type="primary", use_container_width=True):
            # Exemple : ici tu pourrais ajouter des fermetures globales entreprise
            extra_closures = set()  # set([date(year, 8, 1), ...])

            render_member_pdf(
                out_path=out_name,
                year=year,
                member_name=member_name,
                mp=mp,
                closed_weekends=closed_weekends,
                extra_closures=extra_closures,
            )

            with open(out_name, "rb") as f:
                st.download_button(
                    "⬇️ Télécharger le PDF",
                    data=f,
                    file_name=out_name,
                    mime="application/pdf",
                    use_container_width=True
                )

        st.caption("Astuce : tu peux générer un PDF par membre, ou étendre pour générer un PDF unique 'équipe'.")

if __name__ == "__main__":
    main()
