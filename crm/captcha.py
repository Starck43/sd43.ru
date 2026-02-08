import logging
import requests
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CaptchaValidationMixin:
	"""Миксин для проверки Яндекс.Капчи"""

	def get_remote_ip(self):
		"""Получение IP пользователя"""
		request = getattr(self, 'request', None)
		if not request:
			return ''

		x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
		if x_forwarded_for:
			ip = x_forwarded_for.split(',')[0].strip()
		else:
			ip = request.META.get('REMOTE_ADDR', '')
		return ip

	def verify_captcha(self, token):
		"""Проверка Яндекс.Капчи"""
		if not token:
			return False

		# В режиме разработки можно отключить проверку
		if settings.DEBUG and getattr(settings, 'DISABLE_CAPTCHA_IN_DEBUG', True):
			return True

		# URL для проверки (можно переопределить в settings)
		url = getattr(settings, 'YANDEX_CAPTCHA_URL', 'https://smartcaptcha.yandexcloud.net/validate')

		# Получаем ключ из настроек
		server_key = getattr(settings, 'YANDEX_CAPTCHA_SERVER_KEY', '')
		if not server_key:
			# Если ключ не установлен, пропускаем проверку с предупреждением
			logger.warning('YANDEX_CAPTCHA_SERVER_KEY не установлен, пропускаем проверку')
			return True

		try:
			params = {
				'secret': server_key,
				'token': token,
				'ip': self.get_remote_ip(),
			}

			response = requests.get(url, params=params, timeout=10)
			response.raise_for_status()  # Проверяем HTTP ошибки

			result = response.json()
			return result.get('status') == 'ok'

		except requests.exceptions.RequestException as e:
			# Логируем ошибку сети, но пропускаем пользователя
			import logging
			logger = logging.getLogger(__name__)
			logger.error(f'Ошибка при проверке капчи: {e}')
			return getattr(settings, 'CAPTCHA_FAIL_SILENTLY', False)

		except Exception as e:
			import logging
			logger = logging.getLogger(__name__)
			logger.error(f'Неожиданная ошибка при проверке капчи: {e}')
			return getattr(settings, 'CAPTCHA_FAIL_SILENTLY', False)

	def clean(self):
		"""Добавляем проверку капчи к валидации формы"""
		cleaned_data = super().clean()

		# Получаем токен капчи (поле может называться по-разному)
		token = cleaned_data.get('smart_token') or \
		        cleaned_data.get('captcha_token') or \
		        getattr(self, 'cleaned_captcha_token', None)

		if not token:
			# Пробуем получить из request.POST напрямую
			request = getattr(self, 'request', None)
			if request:
				token = request.POST.get('smart-token') or request.POST.get('captcha_token')

		if not self.verify_captcha(token):
			raise ValidationError(
				'Пройдите проверку безопасности. Обновите страницу и попробуйте снова.',
				code='invalid_captcha'
			)

		return cleaned_data
