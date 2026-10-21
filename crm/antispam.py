"""Простые антиспам-механизмы: honeypot-поле и лимит отправок по IP.

Используется вместе с Яндекс SmartCaptcha (`crm.captcha`), но работает
и при её недоступности, чтобы заявки не терялись.
"""

import hashlib
import logging
import time

from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Имя поля-ловушки. Шаблоны пропускают его в общем цикле и рендерят отдельно.
HONEYPOT_FIELD = 'website'


def get_client_ip(request):
	"""IP клиента с учётом reverse proxy (nginx задаёт X-Real-IP)."""
	if request is None:
		return ''

	x_real_ip = request.META.get('HTTP_X_REAL_IP')
	if x_real_ip:
		return x_real_ip.split(',')[0].strip()

	x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		return x_forwarded_for.split(',')[0].strip()

	return request.META.get('REMOTE_ADDR', '')


class HoneypotMixin:
	"""Добавляет скрытое от людей поле: заполненное поле = бот."""

	honeypot_field_name = HONEYPOT_FIELD

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields[self.honeypot_field_name] = forms.CharField(
			label='',
			required=False,
			widget=forms.TextInput(attrs={
				'class': 'hp-field',
				'tabindex': '-1',
				'autocomplete': 'off',
				'aria-hidden': 'true',
				'style': 'position:absolute!important;left:-9999px!important;top:auto!important;'
						 'width:1px!important;height:1px!important;overflow:hidden!important;',
			}),
		)
		# Honeypot всегда последним в порядке отрисовки
		if getattr(self, 'field_order', None):
			self.field_order = [
				name for name in self.field_order if name != self.honeypot_field_name
			] + [self.honeypot_field_name]

	def clean(self):
		# Проверяем ловушку до обращения к API капчи, чтобы не тратить запросы на ботов
		if self.cleaned_data.get(self.honeypot_field_name):
			logger.warning(
				'Antispam: honeypot сработал (ip=%s)',
				get_client_ip(getattr(self, 'request', None)),
			)
			raise ValidationError('Не удалось отправить форму. Попробуйте позже.')
		return super().clean()


def is_rate_limited(request, action, limit=5, period=3600):
	"""Превышен ли лимит отправок action с IP за период (в секундах).

	Fail-open: при недоступности кэша отправка не блокируется.
	"""
	ip = get_client_ip(request)
	if not ip:
		return False

	ip_digest = hashlib.sha256(ip.encode('utf-8')).hexdigest()[:16]
	bucket = int(time.time() // period)
	key = f'antispam:{action}:{ip_digest}:{bucket}'

	try:
		if cache.add(key, 1, period * 2):
			return False
		try:
			count = cache.incr(key)
		except ValueError:
			# Ключ успел истечь между add и incr
			cache.set(key, 1, period * 2)
			return False
		if count > limit:
			logger.warning('Antispam: превышен лимит %s для ip=%s (%s)', action, ip, count)
			return True
		return False
	except Exception:
		logger.exception('Antispam: не удалось проверить лимит %s', action)
		return False