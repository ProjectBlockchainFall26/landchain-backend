"""Django settings. Every value comes from the environment (see .env.example and spec section 14).
Lines marked TODO(<task>) are filled in by that task's owner."""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,api")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # TODO(C2): "django.contrib.gis" once the Parcel boundary uses PostGIS
    "rest_framework",
    "corsheaders",
    # TODO(D1): "drf_spectacular"
    "landchain.core",
    "landchain.accounts",
    "landchain.chain",
    "landchain.indexer",
    "landchain.registry",
    "landchain.fees",
    "landchain.documents",
    "landchain.enquiries",
    "landchain.notifications",
    "landchain.demo",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # TODO(B6): "landchain.core.middleware.ChainHeadersMiddleware"
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# ---- Database: Supabase Postgres (or the local postgis container). Spec 5.6 + 14.
# Without DATABASE_URL we fall back to SQLite so `manage.py check` runs anywhere.
DB_SCHEMA = os.environ.get("DB_SCHEMA", "landchain")
DATABASES = {"default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60)}
if DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})["options"] = f"-c search_path={DB_SCHEMA},public"
# If you use Supabase's transaction pooler (port 6543): DISABLE_SERVER_SIDE_CURSORS=True and CONN_MAX_AGE=0.

# ---- Supabase (A1 / A2)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
SUPABASE_JWT_AUDIENCE = os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")
SUPABASE_DOCS_BUCKET = os.environ.get("SUPABASE_DOCS_BUCKET", "parcel-documents")
DEV_AUTH = env_bool("DEV_AUTH", False)

# ---- Chain (B2 / B4)
CHAIN_ID = int(os.environ.get("CHAIN_ID", "1337"))
RPC_URL = os.environ.get("RPC_URL", "http://127.0.0.1:7545")
RPC_URL_PUBLIC = os.environ.get("RPC_URL_PUBLIC", RPC_URL)
CONTRACTS_DIR = os.environ.get("CONTRACTS_DIR", str(BASE_DIR / "contracts"))
CHAIN_CONFIRMATIONS = int(os.environ.get("CHAIN_CONFIRMATIONS", "0"))
REGISTRAR_SIGNER_KEY = os.environ.get("REGISTRAR_SIGNER_KEY", "")
ID_OFFICER_SIGNER_KEY = os.environ.get("ID_OFFICER_SIGNER_KEY", "")
ADMIN_SIGNER_KEY = os.environ.get("ADMIN_SIGNER_KEY", "")
CHAIN_ALLOW_UNLOCKED_SIGNING = env_bool("CHAIN_ALLOW_UNLOCKED_SIGNING", False) and CHAIN_ID == 1337

# ---- Demo (A6)
DEMO_MODE = env_bool("DEMO_MODE", False)
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")

# ---- Redis / Celery (B1)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# TODO(B1): CELERY_BROKER_URL, CELERY_RESULT_BACKEND, task routes, beat schedule

# ---- SIWE (A4)
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "localhost:5173")
SITE_URI = os.environ.get("SITE_URI", "http://localhost:5173")

# ---- CORS: bearer tokens, no cookies (spec section 4)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = ["authorization", "content-type", "idempotency-key", "x-dev-user"]

REQUIRE_OFFICER_MFA = env_bool("REQUIRE_OFFICER_MFA", False)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # TODO(A2): "landchain.accounts.auth.SupabaseJWTAuthentication",
        # TODO(A2): "landchain.accounts.auth.DevHeaderAuthentication",  (only when DEBUG and DEV_AUTH)
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],  # each view sets its own (C1)
    "UNAUTHENTICATED_USER": None,
    # TODO(B1): "EXCEPTION_HANDLER": "landchain.core.errors.exception_handler",
    # TODO(C1): "DEFAULT_PAGINATION_CLASS": "landchain.core.pagination.Pagination",
    # TODO(D1): "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
