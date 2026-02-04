from django.contrib.auth.models import User
from django.db import models
from django.utils.crypto import get_random_string


class UserModel(models.Model):
	"""
	Базовый миксин для автоматического создания пользователя при сохранении объекта
	"""
	user = models.OneToOneField(
		User,
		on_delete=models.CASCADE,
		null=True,
		blank=True,
		verbose_name='Пользователь'
	)

	class Meta:
		abstract = True

	@property
	def user_name(self):
		if (not self.user.first_name) and (not self.user.last_name):
			return self.user.username
		else:
			return self.user.get_full_name() or f"{self.user.first_name or ''} {self.user.last_name or ''}".strip()

	@staticmethod
	def _generate_username(base_username):
		"""
		Генерация уникального username

		Args:
			base_username: Базовое имя пользователя

		Returns:
			Уникальное имя пользователя или None
		"""
		if not base_username:
			return None

		# Очищаем username от недопустимых символов
		import re
		base_username = re.sub(r'[^\w.@+-]', '', base_username)

		# Если после очистки пустая строка
		if not base_username:
			return None

		# Проверяем базовое имя
		if not User.objects.filter(username=base_username).exists():
			return base_username

		# Пытаемся добавить суффикс
		for i in range(1, 101):
			username = f"{base_username}{i}"
			if not User.objects.filter(username=username).exists():
				return username

		# Если не удалось сгенерировать уникальный username
		import random
		import string
		random_suffix = ''.join(random.choices(string.digits, k=6))
		username = f"{base_username[:20]}_{random_suffix}"

		return username

	def _get_or_create_user(self):
		"""Создает пользователя, если он не существует"""
		if not self.user:
			if hasattr(self, 'email') and self.email:
				existing = User.objects.filter(email=self.email).first()
				if existing:
					self.user = existing
					return True

				username = self._generate_username(self.email.rpartition('@')[0])
			elif hasattr(self, 'slug') and self.slug:
				existing = User.objects.filter(username=self.slug).first()
				if existing:
					self.user = existing
					return True
				username = self.slug
			else:
				return False

			if username:
				raw_password = get_random_string(8)
				user = User.objects.create_user(
					username=username,
					email=getattr(self, 'email', None),
					password=raw_password,
				)
				self.user = user
				return True
		return False

	def save(self, *args, **kwargs):
		"""Переопределяем save, чтобы фильтровать request"""
		# Фильтруем аргументы
		clean_args = []
		for arg in args:
			# Оставляем только допустимые для Model.save() типы
			if arg is None or isinstance(arg, (bool, tuple, str)):
				clean_args.append(arg)
			# Игнорируем request
			elif hasattr(arg, 'META'):
				# Можно сохранить для использования, но не передавать дальше
				self._request = arg
				continue
			else:
				# Оставляем другие аргументы
				clean_args.append(arg)

		self._get_or_create_user()
		super().save(*clean_args, **kwargs)


class BaseImageModel(models.Model):
	IMAGE_FIELDS = ()
	IMAGE_OPTIMIZE_ASYNC = True
	IMAGE_TO_WEBP = True

	class Meta:
		abstract = True

	def save(self, *args, **kwargs):
		is_new = self.pk is None

		super().save(*args, **kwargs)

		if not self.IMAGE_FIELDS:
			return

		from .logic import optimize_image_fields_async, process_image

		# ✔ оптимизируем только если:
		#  - объект новый
		#  - или явно менялись image-поля
		update_fields = kwargs.get('update_fields')
		should_optimize = is_new or (
				update_fields and any(f in update_fields for f in self.IMAGE_FIELDS)
		)

		if not should_optimize:
			return

		if self.IMAGE_OPTIMIZE_ASYNC:
			optimize_image_fields_async(
				self,
				self.IMAGE_FIELDS,
				to_webp=self.IMAGE_TO_WEBP
			)

		else:
			from django.core.files.base import ContentFile

			updated = False
			for field in self.IMAGE_FIELDS:
				file = getattr(self, field)
				if not file:
					continue

				try:
					file.seek(0)  # перематываем на начало
					result = process_image(
						file,
						force_format='WEBP' if self.IMAGE_TO_WEBP else 'JPEG'
					)

					file.save(
						file.name.rsplit('.', 1)[0] + result.extension,
						ContentFile(result.buffer.read()),
						save=False
					)
					updated = True

				except Exception as e:
					import logging
					logger = logging.getLogger(__name__)
					logger.error(f"Error optimizing {field}: {e}")

			if updated:
				super().save(update_fields=self.IMAGE_FIELDS)

	@staticmethod
	def delete_current_file_cache(new_file, current_file=None):
		# Удаляем все кэшированные файлы для этого файла у 'sorl-thumbnails'
		if current_file and current_file != new_file:
			from sorl.thumbnail import delete
			delete(current_file)
