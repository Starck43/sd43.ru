import json
import logging
import requests
from django.conf import settings
from django.core.exceptions import ValidationError


logger = logging.getLogger(__name__)


class CaptchaValidationMixin:
	"""Миксин для проверки Яндекс SmartCaptcha."""

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
		"""Проверяет токен через API Яндекс SmartCaptcha."""
		skip_on_error = getattr(settings, 'CAPTCHA_FAIL_SILENTLY', False)

		# 1. Пропустить проверку если нужно
		if getattr(settings, 'DISABLE_CAPTCHA_IN_DEBUG', False):
			logger.info(f"[INFO] Проверка капчи пропущена. Токен: {token}")
			return True

		# 2. Получить секретный ключ из настроек
		server_key = getattr(settings, 'YANDEX_CAPTCHA_SERVER_KEY', '')
		if not server_key:
			logger.warning("[WARNING] Секретный ключ капчи не найден.")
			return skip_on_error

		# 3. Получить IP-адрес пользователя
		user_ip = self.get_remote_ip()  # Ваш существующий метод

		# 4. Выполнить запрос к API Яндекс SmartCaptcha
		try:
			resp = requests.get(
				getattr(settings, 'YANDEX_CAPTCHA_URL', "https://smartcaptcha.yandexcloud.net/validate"),
				{
					"secret": server_key,
					"token": token,
					"ip": str(user_ip)
				},
				timeout=5
			)

			server_output = resp.content.decode()

			# 5. Обработать ответ (логика из примера)
			if resp.status_code != 200:
				# В случае ошибки сервера капчи решаем "пропустить" человека
				logger.error(f"[ERROR] Ошибка API Яндекс.Капчи. Код: {resp.status_code}, Ответ: {server_output}")
				# Возвращаем True, чтобы не блокировать пользователей из-за сбоев у Яндекса
				return skip_on_error

			# 6. Проверить статус в ответе
			result = json.loads(server_output)
			is_ok = result.get("status") == "ok"

			if settings.DEBUG:
				print(f"[DEBUG] Ответ капчи: {result}. Успех: {is_ok}")
			return is_ok

		except requests.exceptions.RequestException as e:
			# Ошибка сети или таймаута
			logger.error(f"[ERROR] Не удалось проверить капчу (сетевая ошибка): {e}")

		except json.JSONDecodeError as e:
			logger.error(f"[ERROR] Не удалось разобрать ответ от сервера капчи: {e}")

		return skip_on_error

	def clean(self):
		cleaned_data = super().clean()

		all_errors = []

		# Собираем все ошибки полей
		for field, error_list in self.errors.items():
			for error in error_list:
				error_str = str(error).strip()
				if error_str:
					all_errors.append(error_str)

		if all_errors:
			raise ValidationError(all_errors)

		token = cleaned_data.get("smart_token")

		if not token:
			raise ValidationError("Токен капчи не получен сервером.")

		if not self.verify_captcha(token):
			raise ValidationError("Пройдите проверку безопасности.")

		return cleaned_data


