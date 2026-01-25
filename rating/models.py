from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

from exhibition.models import Portfolio
from rating.utils import is_jury_member


class Rating(models.Model):
	"""Рейтинг"""
	STARS = (
		(1, '1 звезда'),
		(2, '2 звезды'),
		(3, '3 звезды'),
		(4, '4 звезды'),
		(5, '5 звезд'),
	)
	user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
	portfolio = models.ForeignKey(
		Portfolio,
		related_name='ratings',
		on_delete=models.CASCADE,
		verbose_name='Портфолио'
	)
	is_jury_rating = models.BooleanField('Оценка жюри', default=False)
	star = models.SmallIntegerField('Оценка', choices=STARS)
	ip = models.CharField("IP адрес", max_length=15)

	created_at = models.DateTimeField('Дата оценки', auto_now_add=True)
	updated_at = models.DateTimeField('Дата изменения', auto_now=True)

	class Meta:
		verbose_name = "Рейтинг"
		verbose_name_plural = "Рейтинги"
		unique_together = ('user', 'portfolio')
		ordering = ['-portfolio__exhibition__date_end', '-updated_at']

	@property
	def fullname(self):
		if self.user:
			if (not self.user.first_name) and (not self.user.last_name):
				return self.user.username
			else:
				return "%s %s" % (self.user.first_name, self.user.last_name)
		else:
			return ''

	fullname.fget.short_description = 'Автор рейтинга'

	def __str__(self):
		jury_mark = " [ЖЮРИ]" if self.is_jury_rating else ""
		return f"{self.star}{jury_mark} - {self.portfolio}"

	@classmethod
	def can_user_rate(cls, user, portfolio):
		"""Проверяет, может ли пользователь выставлять оценку"""
		if not user.is_authenticated:
			return False, "Требуется авторизация"

		# Участник не может оценивать свои работы
		if hasattr(portfolio.owner, 'user') and portfolio.owner.user == user:
			return False, "Вы не можете оценивать свои работы"

		# Проверяем, не оценивал ли уже пользователь
		existing_rating = cls.objects.filter(user=user, portfolio=portfolio).first()
		if existing_rating:
			if is_jury_member(user):
				return True, "Жюри может изменить оценку"
			else:
				return False, "Вы уже оценивали эту работу"

		return True, "Можно оценивать"

	@classmethod
	def can_jury_rate_now(cls, portfolio):
		"""Проверяет, может ли жюри выставлять оценки сейчас"""
		if not portfolio.exhibition:
			return False, "Работа не участвует в выставке"

		# Жюри могут оценивать до 00:00 за день до окончания выставки
		rating_deadline = portfolio.exhibition.date_end - timedelta(days=1)
		if now().date() > rating_deadline:
			return False, "Срок выставления оценок жюри истек"

		return True, "Можно оценивать"

	def calculate(self):
		"""Обновление атрибутов экземпляра рейтинга"""
		stats = self.portfolio.get_rating_stats()
		self.count = stats['count']
		self.total = stats['total']
		self.average = stats['average']
		self.jury_average = stats['jury_average']
		self.jury_count = stats['jury_count']
		return self


class Reviews(models.Model):
	""" Отзывы посетителй на проекты """
	user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, verbose_name='Пользователь')
	parent = models.ForeignKey(
		'self',
		related_name='parent_comments',
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		verbose_name='Родитель'
	)
	group = models.ForeignKey(
		'self',
		related_name='group_comments',
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		verbose_name='Группа'
	)
	portfolio = models.ForeignKey(
		Portfolio, related_name='comments_portfolio', on_delete=models.CASCADE, verbose_name='Портфолио')
	message = models.TextField("Сообщение", max_length=3000)
	posted_date = models.DateTimeField("Опубликовано", auto_now_add=True, blank=True)

	class Meta:
		verbose_name = "Комментарий"
		verbose_name_plural = "Комментарии"
		ordering = ['-posted_date', 'group_id', 'parent_id']
		unique_together = (('id', 'parent'), ('id', 'group'),)

	def count(self):
		aggregates = self.comments_portfolio.aggregate(count=models.Count('portfolio'))
		return aggregates.get('count') or 0

	def reply_count(self):
		aggregates = self.parent_comments.aggregate(count=models.Count('parent'))
		return aggregates.get('count') or 0

	@property
	def fullname(self):
		if self.user:
			if (not self.user.first_name) and (not self.user.last_name):
				return self.user.username
			else:
				return "%s %s" % (self.user.first_name, self.user.last_name)
		else:
			return ''

	fullname.fget.short_description = 'Отзыв от'

	def __str__(self):
		return f"ID{self.id}: {self.user}"
