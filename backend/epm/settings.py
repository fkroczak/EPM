"""
EPM – Django-Einstellungen.

Alle umgebungsabhängigen Werte kommen aus Umgebungsvariablen (backend.env).
Geheimnisse (DB-Passwort, SECRET_KEY) werden aus Dateien gelesen
(Docker Secrets unter /run/secrets), nie aus Variablen.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ("1", "true", "yes", "ja", "on")


def env_list(name, default=""):
    return [x.strip() for x in env(name, default).split(",") if x.strip()]


def geheimnis(name, default=None):
    """Liest NAME_FILE (Pfad) oder, nur in der Entwicklung, NAME direkt."""
    pfad = env(f"{name}_FILE")
    if pfad:
        return Path(pfad).read_text(encoding="utf-8").strip()
    wert = env(name, default)
    if wert is None:
        raise RuntimeError(f"{name}_FILE oder {name} muss gesetzt sein")
    return wert


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = geheimnis("DJANGO_SECRET_KEY", "nur-fuer-entwicklung-unsicher" if DEBUG else None)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

# Django-Admin (/verwaltung/) und API-Browseroberfläche: standardmäßig aus (Sicherheitsprüfung 11.10.2026), ein Admin
# schaltet beide unter Administration › System für eine begrenzte Zeit ein (epm/technik.py). EPM_DJANGO_ADMIN=0/1 bzw.
# EPM_API_BROWSABLE=0/1 in /srv/epm/backend.env legen sie fest – dann gilt der Schalter nicht.
EPM_DJANGO_ADMIN = None if env("EPM_DJANGO_ADMIN", "") == "" else env_bool("EPM_DJANGO_ADMIN")
EPM_API_BROWSABLE = None if env("EPM_API_BROWSABLE", "") == "" else env_bool("EPM_API_BROWSABLE")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "epm",  # Fehlertexte der API (epm/fehlertexte.py)
    "rest_framework",
    "django_filters",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "simple_history",
    "accounts",
    "stammdaten",
    "patienten",
    "infusionen",
    "befunde",
    "berichte",
    "vorlagen",
    "audit",
    "system",
    "altimport",
    "hilfe",
    "scans",
]
INSTALLED_APPS.insert(0, "django.contrib.admin")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "accounts.sitzungen.SitzungMiddleware",
    # aktive Firma (DSKM bzw. Regeneration Clinic, 11.10.2026) – vor allem, was Rechte prüft
    "epm.firma.FirmaMiddleware",
    # /verwaltung/ nur, solange der Schalter an ist (sonst 404)
    "epm.technik.TechnikMiddleware",
    "accounts.sitzungen.RechteStandMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "epm.urls"
WSGI_APPLICATION = "epm.wsgi.application"

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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
        "NAME": env("DB_NAME", "epm"),
        "USER": env("DB_USER", "epm"),
        "PASSWORD": geheimnis("DB_PASSWORD", "epm" if DEBUG else None),
        # Entwicklung (runserver, ein Thread je Anfrage): DB_CONN_MAX_AGE=0, sonst gehen PostgreSQL die Verbindungen aus
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "ATOMIC_REQUESTS": True,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = env("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles"))

# Patientendokumente: Dateisystem, Auslieferung über Nginx (X-Accel-Redirect)
EPM_DOKUMENTE = Path(env("EPM_DOKUMENTE", str(BASE_DIR / "dokumente")))
# Löschliste (Art. 17 DSGVO): endgültig gelöschte Dokumente, nur Nummer, Prüfsumme und Pfad. Liegt bewusst außerhalb
# von Datenbank und Dokumentordner, damit eine Wiederherstellung aus einer älteren Sicherung sie nicht zurücksetzt;
# beim Start holt `epm_loeschungen_nachholen` jede Löschung nach, die eine Wiederherstellung zurückgebracht hat.
EPM_LOESCHLISTE = Path(env("EPM_LOESCHLISTE", str(EPM_DOKUMENTE.parent / "loeschliste" / "loeschliste.jsonl")))
EPM_X_ACCEL = env_bool("EPM_X_ACCEL", not DEBUG)
EPM_X_ACCEL_PREFIX = "/_geschuetzt/dokumente/"
# Systemverwaltung (Administration › System): Aufträge an den Server und dessen Status, gemeinsames Verzeichnis mit
# dem Systemagenten auf dem Server (rollout/epm-systemagent.py). Der Container hat keinen Zugriff auf den Server selbst.
EPM_SYSTEM = Path(env("EPM_SYSTEM", "/data/system"))
# Übernahme der Altdaten (Administration › Import): Hier liegen die Dokumente des Altsystems zum Einlesen
# (<EPM_IMPORT>/PatData/<PatientenID>/…), nur lesbar eingebunden.
EPM_IMPORT = Path(env("EPM_IMPORT", "/data/import"))
EPM_VERSION = env("EPM_VERSION", "")
EPM_UPLOAD_MAX_MB = int(env("EPM_UPLOAD_MAX_MB", "50"))
# Menüpunkt „Scans“ (F160 ff.): hochgeladene Scans bis zur Zuordnung bzw. bis zum Ablauf, getrennt von den
# Dokumenten der Akten. Backend (Hochladen, Zuordnen) und OCR-Dienst (Erkennen) teilen sich das Verzeichnis.
EPM_SCANS = Path(env("EPM_SCANS", str(EPM_DOKUMENTE.parent / "scans")))
EPM_SCANS_MAX_SEITEN = int(env("EPM_SCANS_MAX_SEITEN", "50"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_TEMP_DIR = env("EPM_UPLOAD_TMP", "/tmp")
FILE_UPLOAD_PERMISSIONS = 0o640

# Sitzung: 30 Minuten ohne Aktivität, dann neu anmelden
SESSION_COOKIE_AGE = int(env("EPM_SITZUNG_MINUTEN", "30")) * 60
# Jede Anfrage verlängert die Sitzung – aber nur ihren Ablauf (accounts.sitzungen.SitzungMiddleware). Würde jede Anfrage
# die ganze Sitzung speichern, überschriebe eine langsame ältere Anfrage z. B. den Wechsel der Firma (11.10.2026).
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_NAME = "epm_sitzung"
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_NAME = "epm_csrf"
CSRF_COOKIE_HTTPONLY = False  # das Frontend liest das Token und sendet es als X-CSRFToken

# Hinter Nginx mit TLS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Anmeldung: nach 5 Fehlversuchen bleibt das Konto gesperrt, bis der Admin entsperrt
EPM_LOGIN_MAX_FEHLVERSUCHE = 5
EPM_EINMAL_KENNWORT_STUNDEN = int(env("EPM_EINMAL_KENNWORT_STUNDEN", "48"))

OTP_TOTP_ISSUER = env("EPM_OTP_ISSUER", "EPM")
OTP_TOTP_TOLERANCE = 1

# Passkeys (WebAuthn, Festlegung 08.10.2026): funktionieren nur über einen Namen mit gültigem Zertifikat (eigene CA,
# siehe rollout/epm-zertifikat.sh), nicht über eine IP-Adresse. Adresse(n) wie im Browser, Standard: die Adressen
# aus DJANGO_CSRF_TRUSTED_ORIGINS; RP-ID = Name der ersten Adresse (z. B. epm.stiftung.lan).
EPM_PASSKEY_ORIGINS = env_list("EPM_PASSKEY_ORIGINS", "") or CSRF_TRUSTED_ORIGINS
EPM_PASSKEY_RP_ID = env("EPM_PASSKEY_RP_ID", "")
EPM_PASSKEY_NAME = env("EPM_PASSKEY_NAME", "EPM")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["accounts.permissions.Angemeldet"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "epm.pagination.Seiten",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer",
                                 "rest_framework.renderers.BrowsableAPIRenderer"],
    # die Browseroberfläche nur, solange der Schalter an ist (epm/technik.py)
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "epm.technik.Verhandlung",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anmeldung": "30/min"},
    "COERCE_DECIMAL_TO_STRING": False,
    "EXCEPTION_HANDLER": "epm.api_basis.exception_handler",
}

# Nur ein Prozess schreibt Cache-Werte (Drosselung); lokaler Speicher reicht.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"kurz": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"konsole": {"class": "logging.StreamHandler", "formatter": "kurz"}},
    "root": {"handlers": ["konsole"], "level": env("EPM_LOGLEVEL", "INFO")},
    "loggers": {"django.security": {"level": "WARNING"}},
}
