import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-local-development-key-change-before-production-9f3b7a2c")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = [x for x in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x]
INSTALLED_APPS = ["django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles","corsheaders","rest_framework","marketplace"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware","whitenoise.middleware.WhiteNoiseMiddleware","corsheaders.middleware.CorsMiddleware","django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware","django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
db_url = os.getenv("DATABASE_URL", "sqlite:///" + str(BASE_DIR / "db.sqlite3"))
if db_url.startswith("postgresql://"):
    from urllib.parse import urlparse
    u=urlparse(db_url); DATABASES={"default":{"ENGINE":"django.db.backends.postgresql","NAME":u.path[1:],"USER":u.username,"PASSWORD":u.password,"HOST":u.hostname,"PORT":u.port or 5432,"OPTIONS":{"sslmode":os.getenv("DB_SSLMODE","require")}}}
else: DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR / "db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS=[{"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},{"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator","OPTIONS":{"min_length":12}},{"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},{"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE="en-gb"; TIME_ZONE="UTC"; USE_I18N=True; USE_TZ=True
STATIC_URL="/static/"; STATIC_ROOT=BASE_DIR / "staticfiles"; MEDIA_URL="/media/"; MEDIA_ROOT=BASE_DIR / "media"
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS=[x for x in os.getenv("CORS_ALLOWED_ORIGINS","").split(",") if x]
CORS_ALLOW_CREDENTIALS=True
CSRF_TRUSTED_ORIGINS=[x for x in os.getenv("CSRF_TRUSTED_ORIGINS","").split(",") if x]
SESSION_COOKIE_HTTPONLY=True; SESSION_COOKIE_SAMESITE="Lax"; CSRF_COOKIE_SAMESITE="Lax"
if not DEBUG:
    SESSION_COOKIE_SECURE=True; CSRF_COOKIE_SECURE=True; SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")
    SECURE_SSL_REDIRECT=True; SECURE_HSTS_SECONDS=31536000; SECURE_HSTS_INCLUDE_SUBDOMAINS=True; SECURE_HSTS_PRELOAD=True
REST_FRAMEWORK={"DEFAULT_AUTHENTICATION_CLASSES":["rest_framework.authentication.SessionAuthentication"],"DEFAULT_PERMISSION_CLASSES":["rest_framework.permissions.AllowAny"],"DEFAULT_THROTTLE_CLASSES":["rest_framework.throttling.AnonRateThrottle","rest_framework.throttling.UserRateThrottle"],"DEFAULT_THROTTLE_RATES":{"anon":"120/hour","user":"1000/hour","buyer":"20/hour","login":"10/hour"},"EXCEPTION_HANDLER":"marketplace.api.errors.api_exception_handler"}
PUBLIC_API_URL=os.getenv("PUBLIC_API_URL","http://localhost:8002")
INTEGRATION_SOURCE_SLUG=os.getenv("INTEGRATION_SOURCE_SLUG","dealer-platform")
INTEGRATION_WEBHOOK_SECRET=os.getenv("INTEGRATION_WEBHOOK_SECRET","local-marketplace-secret")
INTEGRATION_PUBLIC_BASE_URL=os.getenv("INTEGRATION_PUBLIC_BASE_URL","http://localhost:8001")
if os.getenv("AWS_STORAGE_BUCKET_NAME"):
    STORAGES={"default":{"BACKEND":"storages.backends.s3.S3Storage"},"staticfiles":{"BACKEND":"whitenoise.storage.CompressedManifestStaticFilesStorage"}}
    AWS_S3_ENDPOINT_URL=os.getenv("AWS_S3_ENDPOINT_URL"); AWS_S3_REGION_NAME=os.getenv("AWS_S3_REGION_NAME","auto"); AWS_S3_CUSTOM_DOMAIN=os.getenv("AWS_S3_CUSTOM_DOMAIN")
