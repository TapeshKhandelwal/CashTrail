# CashTrail API: Django + DRF served by gunicorn.
#   docker build -t cashtrail-backend .
# Runtime configuration comes from environment variables (see .env.example).

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    # gunicorn worker processes; each runs GUNICORN_THREADS threads.
    WEB_CONCURRENCY=2 \
    GUNICORN_THREADS=4

WORKDIR /app

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Code stays owned by root, so the app user can read it but not change it.
COPY . .

# Settings require these to import; collectstatic touches neither the database nor the key.
RUN SECRET_KEY=collectstatic-only DATABASE_URL=postgres://unused@localhost/unused \
    python manage.py collectstatic --noinput \
 && chmod 0755 docker-entrypoint.sh

USER app

EXPOSE 8000

# Sends X-Forwarded-Proto so the check passes whether or not HTTPS redirects are enabled.
HEALTHCHECK --interval=10s --timeout=5s --start-period=180s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request as u; r = u.urlopen(u.Request('http://localhost:8000/api/health/', headers={'X-Forwarded-Proto': 'https'}), timeout=4); sys.exit(0 if r.status == 200 else 1)"]

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --worker-class gthread --threads ${GUNICORN_THREADS} --timeout 60 --access-logfile - --no-control-socket"]
