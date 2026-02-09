from crm import settings
from exhibition.apps import ExhibitionConfig
from exhibition.services import is_mobile
from exhibition.models import Exhibitions


def common_context(request):
	""" Global context processor variables """
	exh_list = Exhibitions.objects.all().only('slug', 'date_start')
	meta = {
		'title': "Дизайнерская выставка Сфера Дизайна",
		'description': "Выставка реализованных дизайн-проектов, где представлены портфолио дизайнеров и победители",
		'keywords': (
			"дизайнерская выставка, реализованные проекты интерьеров, дизайн интерьеров, сфера дизайна, "
			"портфолио дизайнеров, победители выставки"
		)
	}

	scheme = request.is_secure() and "https" or "http"
	site_host = request.META.get('HTTP_HOST', '')

	# Убираем /designers/... из host если есть
	if 'designers/' in site_host:
		site_host = site_host.split('/')[0]  # Берем только доменную часть

	site_url = f'{scheme}://{site_host}'

	# Для поддоменов: если есть X-Subdomain header
	subdomain = request.META.get('HTTP_X_SUBDOMAIN')
	if subdomain:
		site_url = f'{scheme}://{subdomain}.sd43.ru'

	return {
		'is_mobile': is_mobile(request),
		'separator': '|',
		'main_title': ExhibitionConfig.verbose_name,
		'exhibitions_list': exh_list,
		'site_url': site_url,
		'site_host': site_host,
		'scheme': scheme,
		# 'page_url': site_url + request.path,
		'default_meta': meta,
		'default_placeholder': getattr(settings, 'DEFAULT_NO_IMAGE', ''),
	}


def yandex_captcha(request):
	"""Добавляет ключ капчи в контекст всех шаблонов"""
	return {
		'YANDEX_CAPTCHA_CLIENT_KEY': getattr(settings, 'YANDEX_CAPTCHA_CLIENT_KEY', ''),
		'DISABLE_CAPTCHA_IN_DEBUG': getattr(settings, 'DISABLE_CAPTCHA_IN_DEBUG', False),
	}
