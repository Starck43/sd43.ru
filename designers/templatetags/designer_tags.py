from django import template
from django.conf import settings
import os

from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def designer_static(context, path, slug):
	"""Возвращает URL файла, если он существует, иначе пустую строку"""
	# Защита от None
	if not slug:
		return ''

	request = context.get('request')

	# Проверяем STATIC_ROOT
	static_root = getattr(settings, 'STATIC_ROOT', None)
	if not static_root:
		# В разработке без STATIC_ROOT - возвращаем URL без проверки существования
		if hasattr(request, 'subdomain') and request.subdomain and not settings.DEBUG:
			return f'/static/designers/{path}'
		else:
			return f'/static/designers/{slug}/{path}'

	# Определяем путь к файлу
	if hasattr(request, 'subdomain') and request.subdomain and not settings.DEBUG:
		file_path = f'/static/designers/{path}'
		full_path = os.path.join(static_root, 'designers', request.subdomain, path)
	else:
		file_path = f'/static/designers/{slug}/{path}'
		full_path = os.path.join(static_root, 'designers', slug, path)

	# Проверяем существование файла
	try:
		if os.path.exists(full_path):
			return file_path
	except (TypeError, ValueError):
		# Если путь некорректный - возвращаем URL без проверки
		return file_path

	return ''


@register.simple_tag(takes_context=True)
def designer_url(context, view_name, slug=None, **kwargs):
	"""
	Возвращает правильный URL для поддомена или основного домена
	"""
	request = context.get('request')

	# Формируем URL
	if slug:
		url = reverse(view_name, kwargs={'slug': slug, **kwargs})
	else:
		url = reverse(view_name, kwargs=kwargs)

	# На поддомене в продакшене - убираем /designers/{slug} из URL
	is_subdomain = hasattr(request, 'subdomain') and request.subdomain and not settings.DEBUG

	if is_subdomain and slug:
		# Убираем префикс /designers/{slug}/
		prefix = f'/designers/{slug}'
		if url.startswith(prefix):
			return url[len(prefix):]

	return url
