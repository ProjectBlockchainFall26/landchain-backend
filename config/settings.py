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
    "django.contrib.gis",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
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
    "landchain.core.middleware.RequestIdMiddleware",
    "landchain.core.middleware.ChainHeadersMiddleware",
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
# GeoDjango needs PostGIS (task C2), so a postgres:// URL is switched to the PostGIS backend.
DB_SCHEMA = os.environ.get("DB_SCHEMA", "landchain")
DATABASES = {"default": dj_database_url.config(
    default="postgres://landchain:landchain@localhost:5432/landchain",
    conn_max_age=int(os.environ.get("CONN_MAX_AGE", "60")))}
if DATABASES["default"]["ENGINE"] in ("django.db.backends.postgresql", "django.db.backends.postgresql_psycopg2"):
    DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
DATABASES["default"].setdefault("OPTIONS", {})["options"] = f"-c search_path={DB_SCHEMA},public"
DISABLE_SERVER_SIDE_CURSORS = env_bool("DISABLE_SERVER_SIDE_CURSORS", False)
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
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {"notify.relay": {"queue": "default"}}   # signer.send is routed per call (one queue per wallet)
# Local demo without workers: run signer and relay tasks inline, and let ?wait=true run the indexer itself.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = False
INDEXER_INLINE = env_bool("INDEXER_INLINE", CELERY_TASK_ALWAYS_EAGER)
INDEXER_INTERVAL_S = float(os.environ.get("INDEXER_INTERVAL_S", "2" if CHAIN_ID == 1337 else "6"))
CELERY_BEAT_SCHEDULE = {
    "indexer.tick": {"task": "indexer.tick", "schedule": INDEXER_INTERVAL_S},
    "intents.watch": {"task": "intents.watch", "schedule": 3.0},
    "signers.health": {"task": "signers.health", "schedule": 300.0},
    "documents.cleanup": {"task": "documents.cleanup", "schedule": 86400.0},
}

# Cache: rate limits, idempotency locks, chain head. Redis in every real environment.
CACHES = {"default": (
    {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
    if not env_bool("CACHE_LOCMEM", False) else
    {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"})}
RATELIMIT_USE_CACHE = "default"
RATELIMIT_ENABLE = env_bool("RATELIMIT_ENABLE", True)

# ---- Documents vault (D2). Supabase Storage when SUPABASE_URL + service key are set; otherwise a local
# folder (development only), opened through short-lived signed links served by Django.
VAULT_LOCAL_DIR = os.environ.get("VAULT_LOCAL_DIR", str(BASE_DIR / "var" / "vault"))
MAX_UPLOAD_MB = 20
DATA_UPLOAD_MAX_MEMORY_SIZE = 21 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 21 * 1024 * 1024

# ---- Relay (A7 / A8)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_BACKEND = ("django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST
                 else "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "LandChain <no-reply@landchain.local>")
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "")          # "" (log only) | twilio | hubtel
SMS_API_KEY = os.environ.get("SMS_API_KEY", "")
SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "LandChain")
CAPTCHA_SECRET = os.environ.get("CAPTCHA_SECRET", "")
CAPTCHA_VERIFY_URL = os.environ.get("CAPTCHA_VERIFY_URL", "https://challenges.cloudflare.com/turnstile/v0/siteverify")
ENQUIRY_IP_SALT = os.environ.get("ENQUIRY_IP_SALT", SECRET_KEY)

# ---- SIWE (A4)
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "localhost:5173")
SITE_URI = os.environ.get("SITE_URI", "http://localhost:5173")

# ---- CORS: bearer tokens, no cookies (spec section 4)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080")
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_HEADERS = ["authorization", "content-type", "idempotency-key", "x-dev-user"]

REQUIRE_OFFICER_MFA = env_bool("REQUIRE_OFFICER_MFA", False)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "landchain.accounts.auth.SupabaseJWTAuthentication",
        "landchain.accounts.auth.DevHeaderAuthentication",  # active only when DEBUG and DEV_AUTH
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],  # each view sets its own (C1)
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "landchain.core.errors.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "landchain.core.pagination.Pagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "URL_FORMAT_OVERRIDE": None,  # ?format=geojson belongs to GET /parcels
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.MultiPartParser",
                               "rest_framework.parsers.FormParser"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "LandChain API",
    "DESCRIPTION": "Ghana land register on Ethereum. The contract is docs/api-spec.md.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

API_VERSION = "1.0.0"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"landchain": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")}},
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# macOS/Homebrew: point Django at GDAL/GEOS when they aren't on the default search path or the
# installed GDAL is newer than the versions Django tries by name.
if os.environ.get("GDAL_LIBRARY_PATH"):
    GDAL_LIBRARY_PATH = os.environ["GDAL_LIBRARY_PATH"]
if os.environ.get("GEOS_LIBRARY_PATH"):
    GEOS_LIBRARY_PATH = os.environ["GEOS_LIBRARY_PATH"]
SILENCED_SYSTEM_CHECKS = ["gis.W001"]  # GDAL < 3.9 on Ubuntu 24.04 / CI; we never open untrusted spatial files
