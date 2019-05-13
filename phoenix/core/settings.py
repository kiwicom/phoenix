import distutils.util  # pylint: disable=import-error,no-name-in-module
import json
import os
import re

from kw.structlog_config import (  # pylint: disable=no-name-in-module,import-error
    configure_stdlib_logging, configure_structlog
)

DEBUG = distutils.util.strtobool(os.getenv('DEBUG', 'False'))
SECRET_KEY = os.getenv('SECRET_KEY', 'whatasecret')

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'raven.contrib.django.raven_compat',
    'ddtrace.contrib.django',
    'phoenix.core',
    'phoenix.slackbot.apps.SlackbotConfig',
    'phoenix.outages',
    'phoenix.integration',
    'rest_framework',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'stronghold',
    'celerybeat_status',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'stronghold.middleware.LoginRequiredMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'

ROOT_URLCONF = 'phoenix.core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'phoenix.core.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.getenv('DB_HOST', 'postgres'),
        'NAME': os.getenv('DB_NAME', 'postgres'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',  # for /admin
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_ADAPTER = 'phoenix.core.accounts.NoSignupAccountAdapter'
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_ADAPTER = 'phoenix.core.accounts.OpenSignupSocialAccountAdapter'
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'

SITE_ID = 1

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(os.path.dirname(BASE_DIR), 'static_root')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'phoenix.slackbot.auth.SlackAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    )
}


# Logging config
configure_structlog(debug=DEBUG)
configure_stdlib_logging(debug=DEBUG)


REDIS_URL = os.getenv('REDIS_URL', 'redis://redis/0')
if re.match(r'^\d+.\d+.\d+.\d+$', REDIS_URL):
    # URL is actually IP address. In GCP TF will provide redis IP as REDIS_URL.
    redis_ip = os.getenv('REDIS_URL')
    redis_port = os.getenv('REDIS_PORT', '6379')
    redis_db = os.getenv('REDIS_DB', '0')
    REDIS_URL = f'redis://{redis_ip}:{redis_port}/{redis_db}'

CELERY_BROKER_URL = REDIS_URL
CELERY_BROKER_CONNECTION_MAX_RETRIES = 5
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

STRONGHOLD_PUBLIC_URLS = (
    r'^/admin.*?$',  # let Django manage auth for /admin
    r'^/accounts/login/$',
    r'^/accounts/google.*?$',
    r'^/accounts/social/signup/$',
    r'^/slack/announce$',  # slack token verification
    r'^/slack/interaction$',  # slack token verification
    r'^/slack/events$',
    r'^/slack/.*?$',
    r'^/integration/.*?$',
)


ALLOWED_EMAIL_DOMAIN = os.getenv('ALLOWED_EMAIL_DOMAIN')

SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
SLACK_BOT_ID = os.getenv('SLACK_BOT_ID')
SLACK_VERIFICATION_TOKEN = os.getenv('SLACK_VERIFICATION_TOKEN')
SLACK_ANNOUNCE_CHANNEL_ID = os.getenv('SLACK_ANNOUNCE_CHANNEL_ID')
SLACK_EMOJI = os.getenv('SLACK_EMOJI', 'point_up')

# Notify this channel about outage creation
SLACK_NOTIFY_SALES_CHANNEL_ID = os.getenv("SLACK_NOTIFY_SALES_CHANNEL_ID")

SLACK_POSTMORTEM_REPORT_CHANNEL = os.getenv("SLACK_POSTMORTEM_REPORT_CHANNEL")

SMTP_HOST = os.getenv('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_SSL = distutils.util.strtobool(os.getenv('SMTP_SSL', 'True'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
POSTMORTEM_EMAIL_REPORT_FROM = os.getenv("POSTMORTEM_EMAIL_REPORT_FROM")
POSTMORTEM_EMAIL_REPORT_RECIPIENTS = os.getenv("POSTMORTEM_EMAIL_REPORT_RECIPIENTS")

NOTIFY_BEFORE_ETA = int(os.getenv('NOTIFY_BEFORE_ETA', '10'))

# DATADOG
DATADOG_TRACE = {
    'AGENT_HOSTNAME': os.getenv('DATADOG_AGENT_HOSTNAME', 'localhost'),
    'AGENT_PORT': os.getenv('DATADOG_AGENT_PORT', '8126'),
    'TAGS': {
        'env': os.getenv('DATADOG_SERVICE_NAME', 'Phoenix-default'),
    },
}
hostname = os.getenv('DATADOG_TAG_HOST', os.getenv('HOSTNAME'))
if hostname:
    DATADOG_TRACE['TAGS']['host'] = hostname

DATADOG_API_KEY = os.getenv('DATADOG_API_KEY')
DATADOG_APP_KEY = os.getenv('DATADOG_APP_KEY')


RAVEN_CONFIG = {
    'dsn': os.getenv('SENTRY_DSN'),
}

GITLAB_URL = os.getenv('GITLAB_URL')
GITLAB_PRIVATE_TOKEN = os.getenv('GITLAB_PRIVATE_TOKEN')
GITLAB_POSTMORTEM_DAYS_TO_NOTIFY = list(map(int, os.getenv('GITLAB_POSTMORTEM_DAYS_TO_NOTIFY', '3,7').split(',')))
GITLAB_POSTMORTEM_PROJECT = os.getenv('GITLAB_POSTMORTEM_PROJECT')
GITLAB_POSTMORTEM_PROJECT_SLUG = os.getenv('GITLAB_POSTMORTEM_PROJECT_SLUG')

GOOGLE_ACC = os.getenv('GOOGLE_ACC')
GOOGLE_SERVICE_ACCOUNT = os.getenv('GOOGLE_SERVICE_ACCOUNT')
if GOOGLE_SERVICE_ACCOUNT:
    GOOGLE_SERVICE_ACCOUNT = json.loads(GOOGLE_SERVICE_ACCOUNT)

# Specify all limits in hours for example: 48
POSTMORTEM_NOTIFICATION_LIST_LIMIT = int(os.getenv('POSTMORTEM_NOTIFICATION_LIST_LIMIT', '60'))
POSTMORTEM_SLACK_NOTIFICATION_LIMIT = int(os.getenv('POSTMORTEM_SLACK_NOTIFICATION_LIMIT', '12'))
POSTMORTEM_EMAIL_NOTIFICATION_LIMIT = int(os.getenv('POSTMORTEM_EMAIL_NOTIFICATION_LIMIT', '24'))
POSTMORTEM_LABEL_NOTIFICATION_LIMIT = int(os.getenv('POSTMORTEM_LABEL_NOTIFICATION_LIMIT', '48'))

POSTMORTEM_LABEL = os.getenv('POSTMORTEM_LABEL', 'process:wip')
POSTMORTEM_NOTIFICAION_EMAIL_RECIP_ADDR = os.getenv('POSTMORTEM_NOTIFICAION_EMAIL_RECIP_ADDR')

ALLOW_ALL_TO_NOTIFY = distutils.util.strtobool(os.getenv('ALLOW_ALL_TO_NOTIFY', 'False'))
