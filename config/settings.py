"""Django settings. Everything that differs between machines comes from `.env`."""

from datetime import timedelta
from pathlib import Path

from config.env import allowed_hosts, env_bool, env_choice, env_list, env_optional, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG")

# The public host name changes once (mymvz.jnsw.de, later mymvz.de, #10),
# so it lives in .env and nowhere in the code.
SITE_HOST = env_str("SITE_HOST")
ALLOWED_HOSTS = allowed_hosts(SITE_HOST, env_list("DJANGO_EXTRA_HOSTS"), DEBUG)
# Links in e-mails start with this; in development e.g. http://localhost:8000.
SITE_BASE_URL = env_str("SITE_BASE_URL", f"https://{SITE_HOST}").rstrip("/")

# Only invented data until hosting and data protection are settled (#10, #23
# section 8). "synthetic" shows a band on every team page and allows
# `seed_demo`; "real" comes with K9.
DATA_MODE = env_choice("DATA_MODE", ("synthetic", "real"), "synthetic")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "accounts",
    "audit",
    "practice",
    "patients",
    "records",
    "appointments",
    "reporting",
    "telephony",
]

# Must be set before the first migration; changing it later is costly (#5, #25).
AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "accounts.middleware.RequireSecondFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "practice.info.practice_info",
                "config.context_processors.data_mode",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB"),
        "USER": env_str("POSTGRES_USER"),
        "PASSWORD": env_str("POSTGRES_PASSWORD"),
        "HOST": env_str("POSTGRES_HOST", "db"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:account"

# Sessions end after 30 minutes without a request (#25): every request moves
# the expiry forward, and the cookie does not outlive the browser.
SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

OTP_TOTP_ISSUER = "MyMVZ Grevenbroich"

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# One process per container for now (gunicorn without -w, #10), so the
# per-process cache is enough for the per-address limit and the captcha
# replay check. With several workers it needs a shared cache.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# E-mail. Development prints to the console; operation uses an EU provider (#10).
EMAIL_BACKEND = env_str("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env_str("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env_str("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env_optional("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_optional("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL")
# Gets "new request" and "cancelled" without any content (#7).
PRACTICE_NOTIFICATION_EMAIL = env_str("PRACTICE_NOTIFICATION_EMAIL")

# Appointment requests (#5, decisions of 26.09.2026). Defaults until the
# practice names other values.
APPOINTMENTS_VERIFY_EMAIL_WITHIN = timedelta(hours=24)
APPOINTMENTS_CANCELLATION_NOTICE = timedelta(hours=24)
APPOINTMENTS_MAX_WEEKS_AHEAD = 8
APPOINTMENTS_PROPOSAL_WORKING_DAYS = 2
# Calendar days in Europe/Berlin.
APPOINTMENTS_RETENTION_DAYS = 30
# Form submissions per client address and hour (spam protection, #7).
APPOINTMENTS_SUBMISSIONS_PER_HOUR = 10
# Version of the privacy notice shown with the form; stored with each request.
APPOINTMENTS_PRIVACY_NOTICE_VERSION = "2026-09-26"
# Proof of work of the captcha: the client tries on average half of these.
APPOINTMENTS_CAPTCHA_MAX_NUMBER = 300_000

# Key of the internal API for the voice agent (#14 section 7). Empty: the API
# is off (404), never open.
VOICE_API_KEY = env_optional("VOICE_API_KEY")
