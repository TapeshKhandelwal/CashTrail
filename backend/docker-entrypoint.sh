#!/bin/sh
# Container entrypoint: wait for PostgreSQL, apply migrations, optionally load the demo
# dataset, then run the given command (gunicorn by default).
set -eu

echo "entrypoint: waiting for the database (up to ${DB_WAIT_SECONDS:-60}s)"
python - <<'PY'
import os
import sys
import time

import django

django.setup()

from django.db import connection
from django.db.utils import OperationalError

deadline = time.monotonic() + int(os.environ.get("DB_WAIT_SECONDS", "60"))
while True:
    try:
        connection.ensure_connection()
        break
    except OperationalError as exc:
        if time.monotonic() > deadline:
            sys.exit(f"entrypoint: database unavailable: {exc}")
        time.sleep(1)
PY

echo "entrypoint: applying migrations"
python manage.py migrate --noinput

# seed_demo does nothing when the demo users or branches already exist, so restarts and
# rebuilds keep whatever data is in the volume.
if [ "${SEED_DEMO:-false}" = "true" ]; then
    echo "entrypoint: loading demo data if not present"
    python manage.py seed_demo
fi

exec "$@"
