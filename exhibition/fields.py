from django.db import models
from django.utils.translation import gettext_lazy as _
from crm.validators import svg_validator


class AcceptFileField(models.FileField):
	"""Базовое FileField с поддержкой атрибута accept для виджетов"""

	def __init__(self, *args, **kwargs):
		# Сохраняем accept, если он передан
		accept_value = kwargs.pop('accept', None)

		# Если accept передан и он еще не установлен (в дочернем классе)
		if accept_value is not None and not hasattr(self, 'accept'):
			if isinstance(accept_value, str):
				self.accept = [accept_value]
			else:
				self.accept = accept_value
		# Если accept не передан и не установлен, оставляем None
		elif not hasattr(self, 'accept'):
			self.accept = None

		super().__init__(*args, **kwargs)

	def deconstruct(self):
		"""Для корректной работы миграций"""
		name, path, args, kwargs = super().deconstruct()
		if self.accept is not None:
			kwargs['accept'] = self.accept
		return name, path, args, kwargs

	def __eq__(self, other):
		"""Для сравнения в миграциях"""
		if not isinstance(other, AcceptFileField):
			return False
		return (
				self.accept == other.accept and
				super().__eq__(other)
		)


class SVGField(AcceptFileField):
	"""FileField специально для SVG файлов со всеми нужными настройками"""
	description = _("SVG file")

	def __init__(self, verbose_name=None, upload_to=None, **kwargs):
		defaults = {
			'validators': [svg_validator],
			'help_text': _('Загрузите SVG файл'),
		}

		if upload_to is None:
			defaults['upload_to'] = 'svg/'
		else:
			defaults['upload_to'] = upload_to

		# Объединяем с переданными kwargs (переданные значения имеют приоритет)
		for key, value in defaults.items():
			if key not in kwargs:
				kwargs[key] = value

		self.accept = ['.svg']

		if 'accept' in kwargs:
			accept_value = kwargs.pop('accept')
			if isinstance(accept_value, (list, tuple)):
				self.accept = accept_value
			elif isinstance(accept_value, str):
				self.accept = [accept_value]

		super().__init__(verbose_name, **kwargs)

	def deconstruct(self):
		"""Для миграций - удаляем наши кастомные атрибуты"""
		name, path, args, kwargs = super().deconstruct()
		# Удаляем accept, так как он всегда одинаковый для SVGField
		return name, path, args, kwargs
