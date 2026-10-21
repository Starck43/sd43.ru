import json
import logging

import requests
from django.conf import settings
from django.core.exceptions import ValidationError

from crm.antispam import get_client_ip

logger = logging.getLogger(__name__)


class CaptchaValidationMixin:
	"""Миксин для проверки Яндекс SmartCaptcha."""

	def __init__(self, *args, **kwargs):
		# request нужен для передачи IP в API капчи
		self.request = kwargs.pop('request', None)
		super().__init__(*args, **kwargs)

	def get_remote_ip(self):
		"""Получение IP пользователя"""
		return get_client_ip(getattr(self, 'request', None))

	def verify_captcha(self, token):
		"""Проверяет токен через API Яндекс SmartCaptcha."""
		# В debug-режиме проверку можно отключить (для локальной разработки)
		if getattr(settings, 'DISABLE_CAPTCHA_IN_DEBUG', False):
			logger.debug('[INFO] Проверка капчи пропущена (debug).')
			return True

		server_key = getattr(settings, 'YANDEX_CAPTCHA_SERVER_KEY', '')
		if not server_key:
			logger.warning('[WARNING] Секретный ключ капчи не найден.')
			return getattr(settings, 'CAPTCHA_FAIL_SILENTLY', False)

		user_ip = self.get_remote_ip()

		try:
			# POST, а не GET: секрет не должен попадать в логи nginx и прокси
			resp = requests.post(
				getattr(settings, 'YANDEX_CAPTCHA_URL', 'https://smartcaptcha.yandexcloud.net/validate'),
				data={
					'secret': server_key,
					'token': token,
					'ip': str(user_ip),
				},
				timeout=5,
			)

			if resp.status_code != 200:
				logger.error(
					'[ERROR] Ошибка API Яндекс.Капчи. Код: %s, Ответ: %s',
					resp.status_code, resp.text[:500],
				)
				# Не блокируем заявки из-за сбоев на стороне Яндекса
				return getattr(settings, 'CAPTCHA_FAIL_SILENTLY', False)

			result = json.loads(resp.content.decode())
			is_ok = result.get('status') == 'ok'
			logger.debug('[DEBUG] Ответ капчи: %s. Успех: %s', result, is_ok)
			return is_ok

		except requests.exceptions.RequestException as e:
			logger.error('[ERROR] Не удалось проверить капчу (сетевая ошибка): %s', e)
		except (json.JSONDecodeError, UnicodeDecodeError) as e:
			logger.error('[ERROR] Не удалось разобрать ответ от сервера капчи: %s', e)

		return getattr(settings, 'CAPTCHA_FAIL_SILENTLY', False)

	def clean(self):
		cleaned_data = super().clean()

		# Если другие поля уже невалидны, капчу не проверяем
		if self.errors:
			return cleaned_data

		# Капча отключена или не настроена — не блокируем отправку
		captcha_configured = bool(
			getattr(settings, 'YANDEX_CAPTCHA_CLIENT_KEY', '')
			and getattr(settings, 'YANDEX_CAPTCHA_SERVER_KEY', '')
		)
		if getattr(settings, 'DISABLE_CAPTCHA_IN_DEBUG', False) or not captcha_configured:
			return cleaned_data

		token = (cleaned_data.get('smart_token') or '').strip()
		if not token:
			raise ValidationError('Токен капчи не получен сервером.')

		if not self.verify_captcha(token):
			raise ValidationError('Пройдите проверку безопасности.')

		return cleaned_data
