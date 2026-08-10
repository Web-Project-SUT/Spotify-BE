# Streamr backend — Django + DRF served over ASGI (Daphne) for websocket
# support (group listening sessions).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.dev

WORKDIR /app

# psycopg[binary] and Pillow ship manylinux wheels, so no build toolchain is
# needed. Copy requirements first for layer caching.
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

EXPOSE 8000

# Migrate + seed on boot (idempotent), then serve. DATABASE_URL etc. come
# from the environment (see docker-compose.yml).
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo || true; daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
