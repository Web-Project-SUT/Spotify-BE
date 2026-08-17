# Streamr backend — Django + DRF served over ASGI (Daphne) for websocket
# support (group listening sessions).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.dev

WORKDIR /app

# psycopg[binary] and Pillow ship manylinux wheels, so no build toolchain is
# needed. Copy requirements first for layer caching.
#
# The long timeout and retry count are not optional: on a slow or throttled
# link pip gives up on an index request and reports the package as
# "Could not find a version that satisfies the requirement ... (from
# versions: none)", which reads like a missing package rather than a timeout.
COPY requirements/ requirements/
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements/base.txt

COPY . .

EXPOSE 8000

# Migrate + seed on boot (idempotent), then serve. DATABASE_URL etc. come
# from the environment (see docker-compose.yml).
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo || true; daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
