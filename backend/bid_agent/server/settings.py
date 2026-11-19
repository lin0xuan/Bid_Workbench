"""Runtime configuration for the workspace HTTP service."""
import os
from urllib.parse import unquote, urlparse

from bid_agent.core.settings import (
    BUILD_VERSION,
    DATABASE_URL,
    DB_PATH,
    ROOT_PATH,
    env_bool,
)

SECRET_KEY = os.getenv('BID_SECRET_KEY', 'workspace-local-development-key')
DEBUG = env_bool('BID_DEBUG')
ALLOWED_HOSTS = ['*']
APPEND_SLASH = False
ROOT_URLCONF = 'bid_agent.server.urls'
WSGI_APPLICATION = 'bid_agent.server.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
STATIC_URL = f'{ROOT_PATH}/static/' if ROOT_PATH else '/static/'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'bid_agent.apps.accounts',
    'bid_agent.apps.projects',
    'bid_agent.apps.documents',
    'bid_agent.apps.jobs',
    'bid_agent.apps.knowledge',
    'bid_agent.apps.bids',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'bid_agent.server.middleware.ScriptPrefixMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'bid_agent.server.middleware.WorkspaceUserMiddleware',
]

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

REST_FRAMEWORK = {
    'UNAUTHENTICATED_USER': None,
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'EXCEPTION_HANDLER': 'bid_agent.server.exceptions.api_exception_handler',
}


def _database():
    if not DATABASE_URL:
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(DB_PATH),
            'OPTIONS': {
                'timeout': 30,
                'transaction_mode': 'IMMEDIATE',
            },
        }
    parsed = urlparse(DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://', 1))
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parsed.path.lstrip('/'),
        'USER': unquote(parsed.username or ''),
        'PASSWORD': unquote(parsed.password or ''),
        'HOST': parsed.hostname or '',
        'PORT': str(parsed.port or ''),
        'CONN_MAX_AGE': 0,
    }


DATABASES = {'default': _database()}

# Exposed for diagnostics and schema pages.
BUILD = BUILD_VERSION
