"""
Django settings for CashTrail.

All environment-specific values come from environment variables (or a local
`.env` file). See `.env.example` for the full list.
"""

import tempfile
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

from apps.core.api_tags import TAGS

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    JWT_ACCESS_MINUTES=(int, 30),
    JWT_REFRESH_DAYS=(int, 1),
    TRUST_X_FORWARDED_FOR=(bool, False),
    ADMIN_URL=(str, "admin/"),
    SETTLEMENT_SLA_DAYS=(int, 2),
    DUPLICATE_WINDOW_MINUTES=(int, 10),
    PAYMENT_PROVIDER=(str, "mock"),
    LOGIN_THROTTLE_RATE=(str, "10/min"),
    LOGIN_USERNAME_THROTTLE_RATE=(str, "5/min"),
    BFF_SHARED_SECRET=(str, ""),
    USER_THROTTLE_RATE=(str, "600/min"),
    LOG_LEVEL=(str, "INFO"),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Local
    "apps.core",
    "apps.accounts",
    "apps.branches",
    "apps.customers",
    "apps.loans",
    "apps.collections",
    "apps.reconciliation",
    "apps.deposits",
    "apps.payments",
    "apps.dashboard",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database — PostgreSQL only (money columns rely on NUMERIC).

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if test_db_name := env("TEST_DB_NAME", default=None):
    DATABASES["default"]["TEST"] = {"NAME": test_db_name}

# Throttle counters must be shared by every worker process, which a file cache is on one
# host. Point CACHE_URL at Redis when running on several. (A database cache would not do:
# its writes roll back with the request, so failed logins would never count.)
CACHES = {
    "default": env.cache(
        "CACHE_URL", default=f"filecache://{Path(tempfile.gettempdir()) / 'cashtrail-cache'}"
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Email: no feature sends mail; in development anything Django sends goes to the console.

if DEBUG:
    MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}


# Django REST Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "apps.core.schema.DomainAutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exception_handler.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "apps.accounts.throttles.UserRateThrottle",
        "apps.accounts.throttles.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": env("USER_THROTTLE_RATE"),
        "login": env("LOGIN_THROTTLE_RATE"),
        "login_username": env("LOGIN_USERNAME_THROTTLE_RATE"),
        "admin_login": env("LOGIN_THROTTLE_RATE"),
    },
    # Throttle by the address the trusted proxy saw, never by what the client claims.
    "NUM_PROXIES": 1 if env("TRUST_X_FORWARDED_FOR") else 0,
    # Money is serialized as strings ("48500.00"), never floats.
    "COERCE_DECIMAL_TO_STRING": True,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("JWT_ACCESS_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CashTrail API",
    "DESCRIPTION": (
        "Cash Management & Reconciliation System: tracks every repayment from customer "
        "to agent, branch, bank deposit and settlement.\n\n"
        "Authenticate with `POST /api/auth/login/` and send `Authorization: Bearer <access>`. "
        'Money is always a decimal string such as `"48500.00"`. Errors use the shape '
        '`{"error": {"code", "message", "details"}}`.'
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "displayRequestDuration": True},
    "TAGS": TAGS,
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": "apps.accounts.models.User.Role",
        "LoanStatusEnum": "apps.loans.models.Loan.Status",
        "InstallmentStatusEnum": "apps.loans.models.Installment.Status",
        "CollectionModeEnum": "apps.collections.models.Collection.Mode",
        "CollectionStatusEnum": "apps.collections.models.Collection.Status",
        "SubmissionStatusEnum": "apps.reconciliation.models.CashSubmission.Status",
        "DiscrepancyKindEnum": "apps.reconciliation.models.Discrepancy.Kind",
        "DiscrepancyDirectionEnum": "apps.reconciliation.models.Discrepancy.Direction",
        "DiscrepancyStatusEnum": "apps.reconciliation.models.Discrepancy.Status",
        "DiscrepancyReasonCodeEnum": "apps.reconciliation.models.Discrepancy.ReasonCode",
        "DepositSourceEnum": "apps.deposits.models.BankDeposit.Source",
        "DepositStatusEnum": "apps.deposits.models.BankDeposit.Status",
        "GatewayProviderEnum": "apps.payments.models.GatewayProvider",
        "GatewayOrderStatusEnum": "apps.payments.models.GatewayOrder.Status",
    },
}


# Business rules

# A deposit still pending this many days after the deposit date is flagged as delayed.
SETTLEMENT_SLA_DAYS = env("SETTLEMENT_SLA_DAYS")
# Same loan + amount + agent inside this window needs explicit confirmation.
DUPLICATE_WINDOW_MINUTES = env("DUPLICATE_WINDOW_MINUTES")


# Payment gateway (UPI)

PAYMENT_PROVIDER = env("PAYMENT_PROVIDER").lower()
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")
CASHFREE_APP_ID = env("CASHFREE_APP_ID", default="")
CASHFREE_SECRET_KEY = env("CASHFREE_SECRET_KEY", default="")
CASHFREE_ENVIRONMENT = env("CASHFREE_ENVIRONMENT", default="sandbox").lower()
# Optional: where Cashfree posts payment webhooks for each order (https only in production),
# and where it sends the customer back when the checkout cannot open as a pop-up.
CASHFREE_NOTIFY_URL = env("CASHFREE_NOTIFY_URL", default="")
CASHFREE_RETURN_URL = env("CASHFREE_RETURN_URL", default="")
if PAYMENT_PROVIDER not in ("mock", "razorpay", "cashfree"):
    raise ImproperlyConfigured("PAYMENT_PROVIDER must be 'mock', 'razorpay' or 'cashfree'.")
if PAYMENT_PROVIDER == "razorpay" and not (
    RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET and RAZORPAY_WEBHOOK_SECRET
):
    raise ImproperlyConfigured(
        "PAYMENT_PROVIDER=razorpay requires RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET "
        "and RAZORPAY_WEBHOOK_SECRET."
    )
if PAYMENT_PROVIDER == "cashfree":
    if not (CASHFREE_APP_ID and CASHFREE_SECRET_KEY):
        raise ImproperlyConfigured(
            "PAYMENT_PROVIDER=cashfree requires CASHFREE_APP_ID and CASHFREE_SECRET_KEY."
        )
    if CASHFREE_ENVIRONMENT not in ("sandbox", "production"):
        raise ImproperlyConfigured("CASHFREE_ENVIRONMENT must be 'sandbox' or 'production'.")


# CORS / CSRF / proxies

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"
# Enable only behind exactly one proxy that appends the client address to X-Forwarded-For
# (e.g. Render); the right-most entry is then the one the proxy saw.
TRUST_X_FORWARDED_FOR = env("TRUST_X_FORWARDED_FOR")
# Shared with the web app's server, which sends each browser's address in X-Client-IP along
# with this secret; without a match the header is ignored. Empty disables it.
BFF_SHARED_SECRET = env("BFF_SHARED_SECRET")


# Django admin: off unless enabled, and served at a configurable path. Its login sits
# outside the API's throttles, so it is also rate limited per client address.

ADMIN_ENABLED = env.bool("ADMIN_ENABLED", default=DEBUG)
ADMIN_URL = env("ADMIN_URL").strip("/") + "/"


# Production hardening

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # HSTS preload commits the whole registrable domain, which a hosting subdomain is not.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]


# Logging

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_context": {"()": "apps.core.context.RequestContextLogFilter"}},
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname} {name} [{request_id}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["request_context"],
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL")},
}
