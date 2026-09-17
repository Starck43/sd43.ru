import os
from os import getenv
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

from .project import *

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
DOMAIN_URL = 'http://localhost:9000' if DEBUG else f'https://{ALLOWED_HOSTS[0]}'

# Application definition
INSTALLED_APPS = [
	'jazzmin',
	# 'django_static_jquery_ui',
	# 'django_tabbed_changeform_admin',
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.sites',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'django.contrib.sitemaps',
	'django.forms',
	'django_ckeditor_5',
	'sorl.thumbnail',
	'crispy_forms',
	'crispy_bootstrap5',
	'smart_selects',
	'watson',
	'allauth',
	'allauth.account',
	'allauth.socialaccount',
	'allauth.socialaccount.providers.vk',
	'allauth.socialaccount.providers.odnoklassniki',
	'allauth.socialaccount.providers.google',
	'exhibition',
	'rating',
	'blog',
	'ads',
	'designers'
]

MIDDLEWARE = [
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	'django.middleware.cache.FetchFromCacheMiddleware',
	'watson.middleware.SearchContextMiddleware',
	'crm.middleware.AjaxMiddleware',
	'crm.middleware.FixPermissionMiddleware',
	"designers.middleware.SubdomainMiddleware",
	'allauth.account.middleware.AccountMiddleware'
]

if DEBUG:
	INSTALLED_APPS.extend(['debug_toolbar'])
	MIDDLEWARE.extend(['debug_toolbar.middleware.DebugToolbarMiddleware'])

ROOT_URLCONF = 'crm.urls'

INTERNAL_IPS = ['localhost', ]

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [BASE_DIR / 'templates'],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
				'crm.context_processors.common_context',
				'crm.context_processors.yandex_captcha',
			],
		},
	},
]

WSGI_APPLICATION = 'crm.wsgi.application'

# Database configuration
DATABASES = {
	"default": dj_database_url.config(
		default='sqlite:///db.sqlite3',
		conn_max_age=600,
		conn_health_checks=True,
	)
}

# Cache configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
CACHES = {
	'default': {
		'BACKEND': 'django_redis.cache.RedisCache',
		'LOCATION': REDIS_URL,
		'OPTIONS': {
			'CLIENT_CLASS': 'django_redis.client.DefaultClient',
		}
	}
}

# Dev: template fragment cache ({% cache %}) must not survive page refreshes.
# DummyCache stores nothing, so {% cache %} fragments re-render on every request.
if DEBUG:
	CACHES['default'] = {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}

AUTH_PASSWORD_VALIDATORS = [
	{
		'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
		'OPTIONS': {
			'min_length': 6,
		}
	},
	{"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
	{"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = (
	'django.contrib.auth.backends.ModelBackend',
	'allauth.account.auth_backends.AuthenticationBackend',
)

# Provider specific settings
SOCIALACCOUNT_PROVIDERS = {
	'google': {
		'SCOPE': [
			'profile',
			'email',
		],
		'AUTH_PARAMS': {
			'access_type': 'online',
		}
	},
	'odnoklassniki': {
		'SCOPE': ['VALUABLE_ACCESS', 'LONG_ACCESS_TOKEN', 'GET_EMAIL'],
	}
}

SITE_ID = 1

# Основные настройки ALLAUTH
ACCOUNT_LOGIN_METHODS = {'email', 'username'}  # Можно логиниться по email или username
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']  # Поля при регистрации
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_MAX_EMAIL_ADDRESSES = 2

# Email верификация
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 14
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True

# Социальные аккаунты
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_AUTO_SIGNUP = True

# Перенаправления
LOGIN_REDIRECT_URL = "/account/"
ACCOUNT_LOGOUT_ON_GET = True  # Можно оставить, но есть риски CSRF

# Адаптеры и формы
ACCOUNT_ADAPTER = 'exhibition.adapter.CustomAccountAdapter'
ACCOUNT_FORMS = {
	'signup': 'exhibition.forms.AccountSignupForm',
}
SOCIALACCOUNT_FORMS = {
	'signup': 'exhibition.forms.CustomSocialSignupForm',
}

# Email configuration
EMAIL_URL = os.getenv('EMAIL_URL', '')
if EMAIL_URL:
	import urllib.parse

	url = urllib.parse.urlparse(EMAIL_URL)
	MAILERS = {
		"default": {
			"BACKEND": "django.core.mail.backends.smtp.EmailBackend",
			"OPTIONS": {
				"host": url.hostname,
				"port": url.port or 587,
				"username": url.username,
				"password": url.password,
				"use_tls": True if url.scheme == 'smtps' else False,
				"use_ssl": True if url.port == 465 else False,
			},
		},
	}
	DEFAULT_FROM_EMAIL = url.username if url.username else 'webmaster@localhost'

EMAIL_RECIPIENTS = os.getenv('EMAIL_RECIPIENTS', 'saloon.as@gmail.com').split(',')
ADMINS = [('Starck', email) for email in EMAIL_RECIPIENTS]

YANDEX_CAPTCHA_CLIENT_KEY = os.getenv('YANDEX_CAPTCHA_CLIENT_KEY', '')  # Публичный ключ
YANDEX_CAPTCHA_SERVER_KEY = os.getenv('YANDEX_CAPTCHA_SERVER_KEY', '')  # Секретный ключ
YANDEX_CAPTCHA_URL = "https://smartcaptcha.yandexcloud.net/validate"
INVISIBLE_CAPTCHA = os.getenv('INVISIBLE_CAPTCHA', False)
DISABLE_CAPTCHA_IN_DEBUG = False  # Отключать капчу в режиме отладки
CAPTCHA_FAIL_SILENTLY = False  # Что делать при ошибке проверки (True = пропустить)

FILE_UPLOAD_HANDLERS = [
	"django.core.files.uploadhandler.MemoryFileUploadHandler",
	"django.core.files.uploadhandler.TemporaryFileUploadHandler"
]

STORAGES = {
	'default': {
		'BACKEND': 'django.core.files.storage.FileSystemStorage',
	},
	'staticfiles': {
		'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
	},
}

JAZZMIN_SETTINGS = {
	"site_title": "Панель администрирования сайта Сфера Дизайна",
	"site_brand": "Сфера Дизайна",
	"site_logo": "admin/img/brand/sd-logo-icon.jpg",
	"site_icon": "admin/img/brand/sd-logo.jpg",
	"login_logo": "admin/img/brand/sd-logo-default.png",
	# "login_logo_dark": "admin/img/brand/sd-logo-dark.png",
	"welcome_sign": "Администрирование сайта Сфера Дизайна.\n Введите логин и пароль",
	"copyright": f"Компании Арт-Сервис",
	"hide_models": [],
	"order_with_respect_to": [
		'exhibition',
		'exhibition.Exhibitions',
		'exhibition.Categories',
		'exhibition.Nominations',
		'exhibition.Exhibitors',
		'exhibition.Jury',
		'exhibition.Partners',
		'exhibition.Organizer',
		'exhibition.Winners',
		'exhibition.Portfolio',
		'exhibition.PortfolioAttributes',
		'exhibition.Image',
		'exhibition.Gallery',
		'exhibition.Events',
		'exhibition.MetaSEO',
		'rating',
		'blog',
		'ads',
		'designers'
	],
	"changeform_format": "horizontal_tabs",
	# "custom_js": "admin/js/custom.js",
	"topmenu_links": [
		{"name": "Перейти на сайт", "url": DOMAIN_URL, "new_window": True, "permissions": ["auth.view_user"]},
	],
	"usermenu_links": [
		{"name": "Активность", "url": "/account", "new_window": False},
	],
	"icons": {
		"exhibition.Categories": "fas fa-layer-group",
		"exhibition.Nominations": "fas fa-window-restore",
		"exhibition.Portfolio": "fas fa-file-image",
		"exhibition.Gallery": "fas fa-file-image",
		"exhibition.Image": "fas fa-file-image",
		"exhibition.PortfolioAttributes": "fas fa-tags",

		"auth": "fas fa-users-cog",
		"auth.user": "fas fa-user",
		"auth.Group": "fas fa-users",
	},
	"default_icon_parents": "fas fa-chevron-circle-right",
	"default_icon_children": "fas fa-circle",
	"show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
	"navbar_small_text": True,
	"footer_small_text": True,
	"body_small_text": False,
	"brand_small_text": False,
	"brand_colour": False,
	"accent": "accent-indigo",
	"navbar": "navbar-white navbar-light",
	"no_navbar_border": True,
	"navbar_fixed": False,
	"layout_boxed": False,
	"footer_fixed": False,
	"sidebar_fixed": False,
	"sidebar": "sidebar-dark-indigo",
	"sidebar_nav_small_text": False,
	"sidebar_disable_expand": False,
	"sidebar_nav_child_indent": False,
	"sidebar_nav_compact_style": True,
	"sidebar_nav_legacy_style": False,
	"sidebar_nav_flat_style": False,
	"theme": "lux",
	"dark_mode_theme": True,
	"button_classes": {
		"primary": "btn-primary",
		"secondary": "btn-outline-secondary",
		"info": "btn-info",
		"warning": "btn-warning",
		"danger": "btn-danger",
		"success": "btn-success"
	},
	"actions_sticky_top": True
}

# sorl-thumbnail settings
THUMBNAIL_REDIS_URL = os.getenv('THUMBNAIL_REDIS_URL', 'redis://127.0.0.1:6379/1')
if THUMBNAIL_REDIS_URL:
	THUMBNAIL_KVSTORE = 'sorl.thumbnail.kvstores.redis_kvstore.KVStore'

THUMBNAIL_QUALITY = 80
THUMBNAIL_UPSCALE = False
THUMBNAIL_FILTER_WIDTH = 600

ADMIN_THUMBNAIL_QUALITY = 75
ADMIN_THUMBNAIL_SIZE = [60, 60]

DJANGORESIZED_DEFAULT_QUALITY = 80
DJANGORESIZED_DEFAULT_SIZE = [1200, 900]
DJANGORESIZED_DEFAULT_KEEP_META = False

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# CKEditor 5 (django-ckeditor-5)
CKEDITOR_5_FILE_STORAGE = 'exhibition.logic.CkeditorFileStorage'
CKEDITOR_5_ALLOW_ALL_FILE_TYPES = True
CKEDITOR_5_UPLOAD_FILE_TYPES = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'avi', 'mkv', 'mov', 'webm']
CKEDITOR_5_MAX_FILE_SIZE = 5
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"

customColorPalette = [
	{
		'color': 'hsl(4, 90%, 58%)',
		'label': 'Red'
	},
	{
		'color': 'hsl(340, 82%, 52%)',
		'label': 'Pink'
	},
	{
		'color': 'hsl(291, 64%, 42%)',
		'label': 'Purple'
	},
	{
		'color': 'hsl(262, 52%, 47%)',
		'label': 'Deep Purple'
	},
	{
		'color': 'hsl(231, 48%, 48%)',
		'label': 'Indigo'
	},
	{
		'color': 'hsl(207, 90%, 54%)',
		'label': 'Blue'
	},
	{
		'color': '#478631',
		'label': 'Green'
	},
	{
		'color': '#a3c626',
		'label': 'Lime'
	},
]

CKEDITOR_5_CONFIGS = {
	'default': {
		'language': 'ru',
		'blockToolbar': ['paragraph', '|', 'bulletedList', 'numberedList',],
		'toolbar': [
			'heading', 'bold', 'italic', 'underline', 'strikethrough', '|',
			'alignment', 'fontFamily', 'fontColor', 'fontBackgroundColor', 'highlight', '|',
			'outdent', 'indent', 'bulletedList', 'numberedList', 'todoList', '|',
			'removeFormat', 'link', 'blockQuote', 'superscript', 'specialCharacters', 'horizontalLine', '|',
			'insertTable', 'insertImage', 'mediaEmbed', 'fileUpload', '|',
			'code', 'codeBlock', 'htmlEmbed', 'sourceEditing', '|',
			'findAndReplace', 'undo', 'redo',
		],
		'image': {
			'toolbar': ['imageTextAlternative', 'insertImage', '|', 'link', ],
		},
		'table': {
			'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells', 'tableCellProperties'],
			'tableProperties': {
				'borderColors': customColorPalette,
				'backgroundColors': customColorPalette
			},
			'tableCellProperties': {
				'borderColors': customColorPalette,
				'backgroundColors': customColorPalette
			}
		},
		'heading': {
			'options': [
				{'model': 'paragraph', 'view': 'p', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
				{'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
				{'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
				{'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'},
				{'model': 'heading4', 'view': 'h4', 'title': 'Heading 4', 'class': 'ck-heading_heading4'},
			]
		}
	},
	'list': {
		'properties': {
			'styles': 'true',
			'startIndex': 'true',
			'reversed': 'true',
		}
	}
}

X_FRAME_OPTIONS = 'SAMEORIGIN'

LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'formatters': {
		'console': {
			'format': '%(asctime)s [%(levelname)s]: %(message)s'
		},
		'verbose': {
			'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
		},
		'sql': {
			'format': '[SQL] %(duration).3fs %(sql)s %(params)s',
		},
	},
	'handlers': {
		'console': {
			'class': 'logging.StreamHandler',
			'formatter': 'console'
		},
		'thumbnail_console': {
			'class': 'logging.StreamHandler',
			'formatter': 'verbose'
		},
		'sql_console': {
			'class': 'logging.StreamHandler',
			'formatter': 'sql',
		},
		'null': {
			'class': 'logging.NullHandler',
		},
	},
	'loggers': {
		'': {
			'level': 'INFO',
			'handlers': ['console'],
			'propagate': True
		},
		'sorl.thumbnail': {
			'level': 'ERROR',
			'handlers': ['thumbnail_console'],
			'propagate': False,
		},
		'django': {
			'level': 'INFO',
			'handlers': ['console'],
			'propagate': False,
		},
		'django.request': {
			'level': 'WARNING',
			'handlers': ['console'],
			'propagate': False,
		},
		'django.security': {
			'level': 'WARNING',
			'handlers': ['console'],
			'propagate': False,
		},
		'django.db.backends': {
			'level': 'ERROR',
			'handlers': ['console'],
			'propagate': False,
		},
		'exhibition': {
			'level': 'DEBUG',
			'handlers': ['console'],
			'propagate': False,
		},
		'django.contrib.staticfiles': {
			'level': 'ERROR',
			'handlers': ['console'],
			'propagate': False,
		},
		# Настройка Gunicorn
		'gunicorn': {
			'level': 'WARNING',  # Только WARNING и выше
			'handlers': ['console'],
			'propagate': False,
		},
		'gunicorn.access': {
			'handlers': ['null'],  # access-логи полностью отключены
			'propagate': False,
		},
		'gunicorn.error': {
			'level': 'WARNING',  # Ошибки Gunicorn
			'handlers': ['console'],
			'propagate': False,
		},
	}
}

LANGUAGE_CODE = 'ru-RU'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_L10N = True
USE_TZ = True

MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STATIC_URL = 'static/'

if DEBUG:
	STATICFILES_DIRS = [
		BASE_DIR / 'static'
	]
else:
	STATIC_ROOT = os.path.join(BASE_DIR, 'static')

DEFAULT_NO_IMAGE = 'site/default-image.webp'
FILES_UPLOAD_FOLDER = 'uploads/'

FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
MAX_UPLOAD_FILES_SIZE = 25 * 10 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o775

if os.path.exists(os.path.join(MEDIA_ROOT, 'tmp')):
	FILE_UPLOAD_TEMP_DIR = os.path.join(MEDIA_ROOT, 'tmp')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# It uses in exhibition.views.ProjectsList as parameter for queryset
PORTFOLIO_COUNT_PER_PAGE = int(os.getenv('PORTFOLIO_COUNT_PER_PAGE', 20))
# It uses in blog.views.ArticleList as parameter for queryset
ARTICLES_COUNT_PER_PAGE = int(os.getenv('ARTICLES_COUNT_PER_PAGE', 10))
