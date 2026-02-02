from datetime import date

from django.db import models
from django.db.models import Q, Value, CharField

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from blog.models import Article
from exhibition.base_models import BaseImageModel
from exhibition.models import Exhibitors, Partners
from exhibition.logic import MediaFileStorage
from sorl.thumbnail import delete

ads_folder = 'ads/'


class Banner(BaseImageModel):
	IMAGE_FIELDS = ('file',)

	CHOICES = (
		(0, 'горизонтальный'),
		(1, 'вертикальный'),
	)

	title = models.CharField('Название баннера', max_length=100)
	user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Владелец')
	file = models.ImageField(
		'Изображение',
		upload_to=ads_folder,
		storage=MediaFileStorage(),
		null=True,
		blank=True,
		help_text="Вертикальный/горизонтальный баннер для бокового размещения"
	)
	show_start = models.DateField('Начало показа', null=True, blank=True)
	show_end = models.DateField('Окончание показа', null=True, blank=True)
	pages = models.ManyToManyField(
		ContentType,
		related_name='banner_pages',
		blank=True,
		verbose_name='Разделы',
		help_text="Отметьте те разделы, где будет демонстрироваться баннер"
	)
	article = models.ForeignKey(
		Article,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		verbose_name='Статья',
		help_text="Можно указать статью, в конце которой будет показываться баннер"
	)
	ratio = models.SmallIntegerField('Положение', choices=CHOICES, default=0)
	is_general = models.BooleanField(
		'Генеральный партнер ',
		default=False,
		help_text="Баннер партнера отобразится вверху страницы"
	)
	sort = models.IntegerField('Индекс сортировки', null=True, blank=True)

	class Meta:
		verbose_name = 'Баннер'
		verbose_name_plural = 'Баннеры'
		ordering = ['-is_general', '-show_end', 'sort', ]

	# unique_together = ['article']

	def __str__(self):
		return self.title

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.file_current = self.file

	def save(self, *args, **kwargs):
		# если файл заменен, то требуется удалить все миниатюры в кэше у sorl-thumbnails
		if self.file_current and self.file_current != self.file:
			delete(self.file_current)
		super().save(*args, **kwargs)
		self.file_current = self.file

	def delete(self, *args, **kwargs):
		# физически удалим файл и его sorl-миниатюры с диска
		if self.file:
			delete(self.file)

		super().delete(*args, **kwargs)

	@classmethod
	def get_banners(cls, model_name):
		today = date.today()

		banners = cls.objects.filter(
			Q(pages__model=model_name) & (Q(show_start__lte=today) & Q(show_end__gte=today) | Q(is_general=True))
		).annotate(page=Value(model_name, output_field=CharField()))  # добавим значение модели как строка
		return banners

	def owner(self):
		try:
			q = Exhibitors.objects.get(user=self.user)
		except Exhibitors.DoesNotExist:
			try:
				q = Partners.objects.get(user=self.user)
			except Partners.DoesNotExist:
				q = None
		return q

