FROM python:3.12-slim

WORKDIR /app

COPY control-plane/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY control-plane/main.py .
COPY control-plane/routing.py .
COPY control-plane/dashboard.html .
COPY control-plane/desktop.html .
COPY control-plane/workspace.html .
COPY control-plane/activity.html .
COPY control-plane/conversations.html .
COPY control-plane/diario.html .
COPY control-plane/intimo.html .
COPY control-plane/sites.html .
COPY control-plane/spider ./spider
COPY control-plane/connectors ./connectors
COPY control-plane/cp ./cp

COPY shared ./shared
COPY vendor/ecc ./vendor/ecc
COPY vendor/anydoc ./vendor/anydoc
COPY vendor/wayfinder ./vendor/wayfinder
COPY vendor/firecrawl-skills ./vendor/firecrawl-skills
COPY vendor/agency-agents ./vendor/agency-agents
COPY integrations/wayfinder ./integrations/wayfinder

ENV PYTHONPATH=/app:/app/shared

EXPOSE 8085

CMD ["python", "main.py"]
