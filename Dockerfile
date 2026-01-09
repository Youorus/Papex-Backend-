# ─── STAGE 1 : Builder ─────────────────────────────
FROM debian:bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dépendances système nécessaires au build
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
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Création du venv
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dépendances Python (cache friendly)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Code applicatif
COPY . .


# ─── STAGE 2 : Runtime ────────────────────────────
FROM debian:bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Dépendances runtime uniquement
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    wkhtmltopdf \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    xfonts-75dpi \
    xfonts-base \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier le venv propre
COPY --from=builder /opt/venv /opt/venv

# Copier l'app
COPY --from=builder /app /app

EXPOSE 8000

# CMD par défaut (override par Render selon le service)
CMD ["gunicorn", "papex.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
