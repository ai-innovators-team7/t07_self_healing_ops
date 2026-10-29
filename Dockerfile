FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        "google-adk[a2a]==2.11.0" \
        "google-cloud-aiplatform[agent_engines,adk]==1.165.1" \
        "google-genai==2.31.0" \
        "google-cloud-bigquery==3.46.2" \
        "google-cloud-storage==3.17.1" \
        "cloudpickle==3.1.2" \
        "pydantic==2.14.1" \
        "pyyaml==6.0.3" \
        "python-dotenv==1.2.4" \
        "mcp==1.30.0" \
        "fastapi" \
        "uvicorn"

COPY pyproject.toml README.md .env.example ./
COPY app ./app
COPY deploy ./deploy
COPY seed_packs ./seed_packs
COPY ui ./ui

EXPOSE 8080

CMD ["python", "-m", "ui.server", "--host", "0.0.0.0"]
