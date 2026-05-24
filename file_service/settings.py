import os
from configurations import Configuration
import dj_database_url
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rel(*x):
    return os.path.normpath(os.path.join(BASE_DIR, * x))


class BaseConfiguration(Configuration):
    START_TIME = time.time()

    # Database
    # https://docs.djangoproject.com/en/1.11/ref/settings/#databases
    DATABASES = {
        'default': dj_database_url.config(
            default='postgres://fileservice:fileservice@fileservice_postgres/fileservice'
        )
    }

    # Django environ
    # DOTENV = os.path.join(BASE_DIR, '.env')
    
    # SECURITY WARNING: keep the secret key used in production secret!
    SECRET_KEY = '783ae16754d4ce6d1de0a749fb0744f4'
    
    # FIXME: we must setup that list
    ALLOWED_HOSTS = ['*', ]

    INSTALLED_APPS = [

        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.staticfiles',
        'raven.contrib.django.raven_compat',
        'storages',

        'rest_framework',

        'file_service.files',
        'file_service.utils',
        'trood.contrib.django.apps.plugins',
    ]

    TROOD_PLUGINS_PATH = 'plugins'

    MIDDLEWARE = [
        'file_service.utils.middleware.RequestIDMiddleware',
        'django.middleware.security.SecurityMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
    ]

    FILE_GENERATORS = {}

    ROOT_URLCONF = 'file_service.urls'

    REST_FRAMEWORK = {
        'DEFAULT_FILTER_BACKENDS': (
            'rest_framework.filters.OrderingFilter',
            'rest_framework.filters.SearchFilter',
            'trood.contrib.django.filters.TroodRQLFilterBackend',
        ),
        'DEFAULT_PAGINATION_CLASS': 'trood.contrib.django.pagination.TroodRQLPagination',
    }

    TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': ['file_service/templates'],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.template.context_processors.i18n',
                    'django.contrib.messages.context_processors.messages',
                    'django.contrib.auth.context_processors.auth',
                ],
            },
        },
    ]

    WSGI_APPLICATION = 'file_service.wsgi.application'

    LANGUAGES = (
        ('ru-RU', 'Russian'),
        ('en-US', 'English'),
    )

    LANGUAGE_CODE = os.environ.get('LANGUAGE_CODE', 'en-US')

    TIME_ZONE = 'UTC'

    USE_I18N = True

    USE_L10N = True

    USE_TZ = True

    DATE_FORMAT = '%d-%m-%Y'

    # Absolute url
    FILES_BASE_URL = os.environ.get('FILES_BASE_URL', '/media/')

    # Maximum upload size in bytes (default 15MB)
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 15728640))

    # Allowed extensions (comma separated list, e.g. "jpg,png,pdf")
    ALLOWED_EXTENSIONS = os.environ.get('ALLOWED_EXTENSIONS', '')
    if ALLOWED_EXTENSIONS:
        ALLOWED_EXTENSIONS = [ext.strip().lower() for ext in ALLOWED_EXTENSIONS.split(',')]
    else:
        ALLOWED_EXTENSIONS = []

    STORAGE_TYPE = os.environ.get('STORAGE_TYPE', 'DISK')

    STATIC_URL = '/static/'
    STATIC_ROOT = os.environ.get('FILE_SERVICE_STATIC_ROOT', rel('static'))

    MEDIA_URL = '/media/'

    if STORAGE_TYPE == "DISK":
        MEDIA_ROOT = os.environ.get('FILE_SERVICE_MEDIA_ROOT', rel('media'))

    if STORAGE_TYPE == 'DO_SPACES':
        DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

        AWS_ACCESS_KEY_ID = os.environ.get('SPACES_ACCESS_KEY')
        AWS_SECRET_ACCESS_KEY = os.environ.get('SPACES_SECRET_ACCESS_KEY')
        AWS_STORAGE_BUCKET_NAME = os.environ.get('SPACES_BUCKET')
        AWS_S3_ENDPOINT_URL = 'https://fra1.digitaloceanspaces.com'
        AWS_S3_OBJECT_PARAMETERS = {
            'CacheControl': 'max-age=86400',
        }

        MEDIA_ROOT = os.environ.get('FILE_SERVICE_MEDIA_ROOT', 'media')

        AWS_LOCATION = os.path.join(os.environ.get('SPACES_PATH', ''), MEDIA_ROOT)
        AWS_DEFAULT_ACL = os.environ.get('SPACES_DEFAULT_PERMISSIONS', 'public-read')

    IMAGE_SIZES = {
        'small': 128,
        'medium': 320,
        'large': 640,
        'xlarge': 1200
    }

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'root': {
            'level': 'WARNING',
            'handlers': ['sentry'],
        },
        'filters': {
            'request_id': {
                '()': 'file_service.utils.logging_utils.RequestIDFilter',
            }
        },
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s '
                          '%(process)d %(thread)d %(message)s'
            },
            'json': {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s'
            },
        },
        'handlers': {
            'sentry': {
                'level': 'WARNING',
                'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
                'tags': {'custom-tag': 'x'},
            },
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'filters': ['request_id'],
                'formatter': 'json' if os.environ.get('JSON_LOGS', 'False') == 'True' else 'verbose'
            }
        },
        'loggers': {
            'django.db.backends': {
                'level': 'ERROR',
                'handlers': ['console'],
                'propagate': False,
            },
            'file_service': {
                'level': 'INFO',
                'handlers': ['console', 'sentry'],
                'propagate': False,
            },
            'raven': {
                'level': 'DEBUG',
                'handlers': ['console'],
                'propagate': False,
            },
            'sentry.errors': {
                'level': 'DEBUG',
                'handlers': ['console'],
                'propagate': False,
            },
        },
    }

    ENABLE_RAVEN = os.environ.get('ENABLE_RAVEN', "False")

    if ENABLE_RAVEN == "True":
        RAVEN_CONFIG = {
            'dsn': os.environ.get('RAVEN_CONFIG_DSN'),
            'release': os.environ.get('RAVEN_CONFIG_RELEASE')
        }

    AUTH_TYPE = os.environ.get('AUTHENTICATION_TYPE')

    if AUTH_TYPE == 'TROOD':
        TROOD_AUTH_SERVICE_URL = os.environ.get(
            'TROOD_AUTH_SERVICE_URL', 'http://authorization.trood:8000/'
        )
        TROOD_ABAC = {
            'RULES_SOURCE': os.environ.get("ABAC_RULES_SOURCE", "URL"),
            'RULES_PATH': os.environ.get("ABAC_RULES_PATH", "{}api/v1.0/abac/".format(TROOD_AUTH_SERVICE_URL))
        }
        SERVICE_DOMAIN = os.environ.get("SERVICE_DOMAIN", "FILESERVICE")
        SERVICE_AUTH_SECRET = os.environ.get("SERVICE_AUTH_SECRET")

        REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (
           'trood.contrib.django.auth.authentication.TroodTokenAuthentication',
        )

        MIDDLEWARE = MIDDLEWARE + [
            'trood.contrib.django.auth.middleware.TroodABACMiddleware',
        ]

        REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = (
            'trood.contrib.django.auth.permissions.TroodABACPermission',
        )

        REST_FRAMEWORK['DEFAULT_FILTER_BACKENDS'] += (
            'trood.contrib.django.auth.filter.TroodABACFilterBackend',
        )

    elif AUTH_TYPE == 'NONE':
        REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = ()
        REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'] = ()


class Development(BaseConfiguration):
    DEBUG = True


class Production(BaseConfiguration):
    DEBUG = False
