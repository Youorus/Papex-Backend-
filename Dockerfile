# ─── STAGE 1 : Builder ─────────────────────────────
FROM debian:bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installer Python 3.11 et dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    build-essential \
    libpq-dev \
    curl \
    git \
    wkhtmltopdf \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    xfonts-75dpi \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# Définir Python 3.11 comme python par défaut
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

# Étape de cache : requirements.txt
COPY requirements.txt .
RUN pip install --upgrade pip --break-system-packages \
    && pip install --break-system-packages -r requirements.txt

# Copier le projet complet
COPY . .



# ─── STAGE 2 : Final ───────────────────────────────
FROM debian:bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installer Python 3.11 + wkhtmltopdf + libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    wkhtmltopdf \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    xfonts-75dpi \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/*

# Définir Python 3.11 comme python par défaut
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

# Copier les dépendances Python déjà installées
COPY --from=builder /usr/local /usr/local

# Copier l'application
COPY --from=builder /app /app

EXPOSE 8000

# Lancement ASGI via Gunicorn
CMD ["gunicorn", "tds.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]