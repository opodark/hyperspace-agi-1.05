# SPDX-License-Identifier: Apache-2.0
# Scout notturno isolato: browser-use + Chromium in un container senza privilegi.
# Build:  docker build -t hyperspace/browser-scout:0.13.14 integrations/browser-scout
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IN_DOCKER=true \
    HOME=/tmp/home \
    XDG_CONFIG_HOME=/tmp/home/.config \
    ANONYMIZED_TELEMETRY=false \
    BROWSER_USE_CLOUD_SYNC=false \
    BROWSER_USE_DISABLE_EXTENSIONS=1 \
    BROWSER_USE_LOGGING_LEVEL=info

RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-noto-core fonts-noto-color-emoji ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Versione bloccata: un aggiornamento di browser-use si fa a mano, rileggendo
# le opzioni di isolamento usate in scout.py.
RUN pip install "browser-use==0.13.14"

RUN useradd --system --uid 10001 --create-home --home-dir /home/scout scout \
 && mkdir -p /in /out && chown scout:scout /out
COPY scout.py /app/scout.py

USER scout
WORKDIR /app
ENTRYPOINT ["python", "/app/scout.py"]
