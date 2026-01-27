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

