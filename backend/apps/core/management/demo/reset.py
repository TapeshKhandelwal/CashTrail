from django.apps import apps
from django.db import connection

# Every app that owns CashTrail data; framework tables that reference users (refresh tokens,
# admin log) are emptied through CASCADE.
DATA_APPS = (
    "accounts",
    "branches",
    "customers",
    "loans",
    "collections",
    "reconciliation",
    "deposits",
    "payments",
    "audit",
    "core",
)


def wipe_data() -> None:
    """Empty every CashTrail table and restart its ids.

    The integrity triggers reject row deletes on financial and audit tables, and they are kept
    enabled on purpose. TRUNCATE is not a row delete, so it clears the tables without switching
    any protection off (and without needing superuser rights to disable triggers).
    """
    tables = sorted(
        {
            model._meta.db_table
            for label in DATA_APPS
            for model in apps.get_app_config(label).get_models(include_auto_created=True)
        }
    )
    with connection.cursor() as cursor:
        # Rows inserted earlier in this transaction leave deferred FK checks queued, and
        # PostgreSQL refuses to truncate a table with pending trigger events.
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute(
            f"TRUNCATE {', '.join(map(connection.ops.quote_name, tables))} RESTART IDENTITY CASCADE"
        )
