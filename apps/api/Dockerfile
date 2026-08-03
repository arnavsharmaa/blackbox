FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY apps/api/pyproject.toml apps/api/
COPY apps/api/blackbox_api apps/api/blackbox_api
RUN pip install --no-cache-dir ./apps/api

COPY packages/sample-data packages/sample-data
COPY scripts/seed.py scripts/seed.py

RUN useradd --create-home blackbox \
    && mkdir -p /app/data \
    && chown -R blackbox:blackbox /app
USER blackbox

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

CMD ["sh", "-c", "python scripts/seed.py && uvicorn blackbox_api.main:app --host 0.0.0.0 --port 8000"]
