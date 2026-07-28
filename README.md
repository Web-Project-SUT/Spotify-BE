# Spotify-BE

Django/DRF backend for the Spotify clone.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements/dev.txt
createdb spotify_be
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 8000
```

Create a `.env` file (not committed) with:

```
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://ava@localhost:5432/spotify_be
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

API docs at `http://localhost:8000/api/docs/`.

## Tests

```bash
pytest --cov=apps --cov-report=term-missing
# or
python manage.py test
```

## Lint

```bash
ruff check .
ruff format --check .
```
