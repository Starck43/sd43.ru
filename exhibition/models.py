import re
from datetime import timedelta
from os import path, rename, rmdir, listdir

from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.validators import RegexValidator
from django.db.models import F
from django.db.models.functions import Coalesce
# from django.utils.text import slugify
from django.urls import reverse  # Used to generate URLs by reversing the URL patterns
from django.utils import timezone
from django.utils.timezone import now
from smart_selects.db_fields import ChainedForeignKey
# from django.core.files.base import ContentFile
from sorl.thumbnail import delete
from uuslug import uuslug

from crm import models
from .base_models import UserModel, BaseImageModel
from .fields import SVGField
from .logic import (
	MediaFileStorage, portfolio_upload_to, cover_upload_to, gallery_upload_to, limit_file_size
)
from .services import update_google_sitemap

LOGO_FOLDER = 'logos/'
BANNER_FOLDER = 'banners/'


class PersonManager(models.Manager):
	def get_queryset(self):
		return super().get_queryset().filter(status=True)


class Person(UserModel, BaseImageModel, models.Model):
	""" Abstract model for Exhibitors, Organizer, Jury, Partners """

	IMAGE_FIELDS = ('logo',)
	CHOICES = (
		(True, 'Доступен'),
		(False, 'Скрыт')
	)

	logo = models.ImageField(
		'Логотип',
		upload_to=LOGO_FOLDER,
		storage=MediaFileStorage(image_size=[450, 450]),
		null=True,
		blank=True
	)
	name = models.CharField('Имя контакта', max_length=100)
	slug = models.SlugField('Ярлык', max_length=100, unique=True)
	description = RichTextUploadingField('Информация о контакте', blank=True)
	status = models.BooleanField('Видимость на сайте', choices=CHOICES, default=True)
	sort = models.IntegerField('Индекс сортировки', null=True, blank=True)

	objects = PersonManager()

	class Meta:
		abstract = True

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.original_logo = getattr(self, 'logo', None)
		self.original_slug = getattr(self, 'slug', None)

	def handle_slug_change(self, current_slug: str = None):
		"""Обработка изменения slug. Переопределяется в дочерних классах при необходимости."""
		if not current_slug or current_slug == self.slug:
			return

		portfolio_folder = path.join(settings.MEDIA_ROOT, settings.FILES_UPLOAD_FOLDER, self.original_slug)
		if path.exists(portfolio_folder):
			new_portfolio_folder = path.join(settings.MEDIA_ROOT, settings.FILES_UPLOAD_FOLDER, self.slug)
			# переименуем имя папки с проектами текущего участника
			rename(portfolio_folder, new_portfolio_folder)

			# почистим кэшированные файлы и изменим путь к файлам в таблице Image
			owner_images = Image.objects.filter(portfolio__owner__slug=self.original_slug)
			for image in owner_images:
				# Only clears key-value store data in thumbnail-kvstore, but does not delete image file
				delete(image.file, delete_file=False)
				renamed_file = str(image.file).replace(current_slug, self.slug)
				image.file = renamed_file
				image.save()

	def delete(self, *args, **kwargs):
		delete(self.logo)

		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)

		if not self.slug:
			self.slug = uuslug(self.name.lower(), instance=self)

		self.delete_current_file_cache(self.logo, self.original_logo)
		self.handle_slug_change(self.original_slug)

		super().save(*args, **kwargs)
		self.original_logo = self.logo
		self.original_slug = self.slug

	def __str__(self):
		return self.name


class Profile(models.Model):
	""" Abstract model for Exhibitors and Partners """
	phone_regex = RegexValidator(
		regex=r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$',
		message="Допустимы цифры, знак плюс, символы пробела и круглые скобки"
	)
	address = models.CharField('Адрес', max_length=100, blank=True)
	phone = models.CharField('Контактный телефон', validators=[phone_regex], max_length=18, blank=True)
	email = models.EmailField('E-mail', max_length=75, blank=True)
	site = models.URLField('Сайт', max_length=75, blank=True)
	instagram = models.CharField('Instagram', max_length=75, blank=True, default="")
	tg = models.CharField('Телеграм', max_length=75, blank=True, default='https://tg.me')
	vk = models.CharField('Вконтакте', max_length=75, blank=True, default="https://vk.com")

	class Meta:
		abstract = True

	def __iter__(self):
		for field in self._meta.fields:
			name = field.name
			label = field.verbose_name
			value = field.value_to_string(self)
			link = None
			if value and type(field.default) is str:
				value = value.rsplit('/', 1)[-1]
				link = field.default + '/' + value.lower()

			if value and name in ['phone', 'email']:
				prefix = 'tel' if name == 'phone' else 'mailto'
				link = prefix + ':' + value.lower()

			if name in ['description', 'vk', 'tg', 'instagram']:
				label = ''

			if name == 'site' and value:
				value = re.sub(r'^https?:\/\/|\/$', '', value, flags=re.MULTILINE)
				link = 'https://' + value

			if (name == 'address' or name == 'site' or link) and value:
				yield (name, label, value, link)


class Exhibitors(Person, Profile):
	class Meta(Person.Meta):
		verbose_name = 'Участник выставки'
		verbose_name_plural = 'Участники выставки'
		ordering = ['user__last_name']
		unique_together = ['user', ]
		db_table = 'exhibitors'

	def get_absolute_url(self):
		return reverse('exhibition:exhibitor-detail-url', kwargs={'slug': self.slug})


class Organizer(Person, Profile):
	class Meta(Person.Meta):
		verbose_name = 'Организатор'
		verbose_name_plural = 'Организаторы'
		db_table = 'organizers'
		ordering = ['sort', 'name']


class Jury(Person):
	excerpt = models.CharField('Краткое описание', max_length=255, null=True, blank=True)

	class Meta(Person.Meta):
		verbose_name = 'Жюри'
		verbose_name_plural = 'Жюри'
		ordering = [Coalesce("sort", F('id') + 500)]  # сортировка в приоритете по полю sort, а потом уже по-умолчанию
		db_table = 'jury'

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()

	def get_absolute_url(self):
		return reverse('exhibition:jury-detail-url', kwargs={'slug': self.slug})


class Partners(Person, Profile):
	class Meta(Person.Meta):
		verbose_name = 'Партнер выставки'
		verbose_name_plural = 'Партнеры'
		db_table = 'partners'
		ordering = [Coalesce("sort", F('id') + 500)]  # сортировка в приоритете по полю sort, а потом уже по-умолчанию

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()

	def get_absolute_url(self):
		return reverse('exhibition:partner-detail-url', kwargs={'slug': self.slug})


class Categories(models.Model):
	""" Таблица Категорий """

	title = models.CharField('Категория', max_length=150)
	slug = models.SlugField('Ярлык', max_length=150, unique=True)
	description = models.TextField('Описание категории', blank=True)
	logo = SVGField(
		'Логотип',
		upload_to=LOGO_FOLDER,
		storage=MediaFileStorage(),
		null=True,
		blank=True,
		help_text='Загрузите SVG файл',
	)
	sort = models.IntegerField('Индекс сортировки', null=True, blank=True)

	class Meta:
		ordering = ['sort', 'title']
		verbose_name = 'Категория'
		verbose_name_plural = 'Категории'
		db_table = 'categories'

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = uuslug(self.title.lower(), instance=self)
		super().save(*args, **kwargs)
		update_google_sitemap()

	def __str__(self):
		return self.title if self.title else '<без категории>'

	def get_absolute_url(self):
		return reverse('exhibition:projects-list-url', kwargs={'slug': self.slug})


class Nominations(models.Model):
	""" Таблица Номинаций """
	category = models.ForeignKey(Categories, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Категория')
	title = models.CharField('Номинация', max_length=150)
	slug = models.SlugField('Ярлык', max_length=150, unique=True)
	description = RichTextUploadingField('Описание номинации', blank=True)
	sort = models.IntegerField('Индекс сортировки', null=True, blank=True)

	class Meta:
		ordering = ['sort', 'title']
		verbose_name = 'Номинация'
		verbose_name_plural = 'Номинации'
		db_table = 'nominations'

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = uuslug(self.title.lower(), instance=self)
		super().save(*args, **kwargs)
		update_google_sitemap()

	def __str__(self):
		return self.title

	def get_absolute_url(self):
		if self.category:
			return reverse('exhibition:projects-list-url', kwargs={'slug': self.category.slug})
		else:
			return reverse('exhibition:category-list-url', kwargs={'slug': None})


class Exhibitions(BaseImageModel):
	""" Таблица Выставки """
	IMAGE_FIELDS = ('banner',)

	title = models.CharField('Название выставки', max_length=150)
	slug = models.SlugField('Ярлык', max_length=150, unique=True)
	banner = models.ImageField(
		'Баннер',
		storage=MediaFileStorage(image_size=[1200, 800]),
		upload_to=BANNER_FOLDER,
		null=True,
		blank=True
	)
	description = RichTextUploadingField('Описание выставки', blank=True)
	date_start = models.DateTimeField('Начало выставки', unique=True)
	date_end = models.DateTimeField('Окончание выставки', unique=True)
	location = models.CharField('Расположение выставки', max_length=200, blank=True)
	exhibitors = models.ManyToManyField(
		Exhibitors,
		related_name='exhibitors_for_exh',
		verbose_name='Участники выставки',
		blank=True
	)
	partners = models.ManyToManyField(
		Partners,
		related_name='partners_for_exh',
		verbose_name='Партнеры выставки',
		blank=True
	)
	jury = models.ManyToManyField(
		Jury,
		related_name='jury_for_exh',
		verbose_name='Жюри выставки',
		blank=True
	)
	nominations = models.ManyToManyField(
		Nominations,
		related_name='nominations_for_exh',
		verbose_name='Номинации',
		blank=True
	)

	class Meta:
		ordering = ['-date_start']
		verbose_name = 'Выставка'
		verbose_name_plural = 'Выставки'
		db_table = 'exhibitions'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.current_banner = self.banner

	def delete_cached_banner(self):
		# физически удалим файл с диска, если он единственный
		if len(Exhibitions.objects.filter(banner=self.banner.name)) == 1:
			delete(self.banner)

	def delete_related_gallery(self):
		for gallery in self.gallery.all():
			gallery.delete()

	def delete(self, *args, **kwargs):
		self.delete_cached_banner()
		self.delete_related_gallery()

		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = uuslug(self.date_start.strftime('%Y'), instance=self)

		self.delete_current_file_cache(self.banner, self.current_banner)

		super().save(*args, **kwargs)
		self.current_banner = self.banner

	def __str__(self):
		return self.title

	@classmethod
	def get_unfinished_exhibition(cls):
		"""Получить текущую или предстоящую выставку (не завершенную)"""
		return (
			cls.objects
			.filter(date_end__gte=now)
			.order_by('date_start')
			.first()
		)

	@property
	def jury_deadline(self):
		return (
				self.date_start
				.replace(hour=0, minute=0, second=0, microsecond=0)
				+ timedelta(days=1)
		)

	@property
	def is_jury_voting_active(self):
		"""Активно ли голосование жюри (до начала выставки)"""
		return timezone.now() < self.jury_deadline

	@property
	def is_users_voting_active(self):
		"""Дедлайн для всех пользователей (после выставки)"""
		return timezone.now() >= self.date_end

	@property
	def is_exhibition_active(self):
		return self.date_start <= timezone.now() < self.date_end

	@property
	def is_exhibition_ended(self):
		return timezone.now() >= self.date_end

	@property
	def exh_year(self):
		return self.date_start.strftime('%Y')

	def get_absolute_url(self):
		return reverse('exhibition:exhibition-detail-url', kwargs={'exh_year': self.slug})


class Winners(models.Model):
	""" Таблица Победителей """
	exhibition = models.ForeignKey(
		Exhibitions,
		related_name='exhibition_for_winner',
		on_delete=models.CASCADE,
		null=True,
		verbose_name='Выставка'
	)
	nomination = ChainedForeignKey(
		Nominations,
		chained_field="exhibition",
		chained_model_field="nominations_for_exh",
		show_all=False,
		auto_choose=True,
		sort=True,
		related_name='nomination_for_winner',
		on_delete=models.CASCADE,
		null=True,
		verbose_name='Номинация'
	)
	exhibitor = ChainedForeignKey(
		Exhibitors,
		chained_field="exhibition",
		chained_model_field="exhibitors_for_exh",
		show_all=False,
		auto_choose=True,
		sort=True,
		related_name='exhibitor_for_winner', on_delete=models.CASCADE, null=True,
		verbose_name='Победители выставки'
	)
	portfolio = ChainedForeignKey(
		'Portfolio',
		chained_field="exhibitor",
		chained_model_field="owner",
		show_all=False,
		auto_choose=True,
		sort=True,
		related_name='portfolio_for_winner', on_delete=models.SET_NULL, null=True,
		verbose_name='Проект'
	)

	class Meta:
		ordering = ['-exhibition']
		verbose_name = 'Победитель выставки'
		verbose_name_plural = 'Победители'
		db_table = 'winners'
		unique_together = ['exhibition', 'exhibitor', 'nomination']

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()

	def __str__(self):
		return '%s | %s, %s' % (self.exhibitor.name, self.nomination.title, self.exhibition.slug)

	def name(self):
		return self.exhibitor.name

	name.short_description = 'Победитель'

	def get_absolute_url(self):
		return reverse(
			'exhibition:winner-detail-url',
			kwargs={'exh_year': self.exhibition.slug, 'slug': self.nomination.slug}
		)


class Events(models.Model):
	""" Таблица Мероприятий """
	exhibition = models.ForeignKey(
		Exhibitions,
		on_delete=models.SET_NULL,
		related_name='events',
		verbose_name='Выставка',
		null=True,
		blank=True,
	)
	title = models.CharField('Название мероприятия', max_length=250)
	date_event = models.DateField('Дата мероприятия')
	time_start = models.TimeField('Начало мероприятия')
	time_end = models.TimeField('Окончание мероприятия')
	location = models.CharField('Зона проведения', max_length=75, blank=True)
	hoster = models.CharField('Участник мероприятия', max_length=75)
	lector = models.CharField('Ведущий мероприятия', max_length=75)
	description = RichTextUploadingField('Описание мероприятия', blank=True)

	# Metadata
	class Meta:
		ordering = ['date_event', 'time_start']
		verbose_name = 'Мероприятие'
		verbose_name_plural = 'Мероприятия'
		db_table = 'events'

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()

	def __str__(self):
		return self.title

	def time_event(self):
		return "%s - %s" % (self.time_start.strftime('%H:%M'), self.time_end.strftime('%H:%M'))

	time_event.short_description = 'Время мероприятия'

	def get_absolute_url(self):
		return reverse('exhibition:event-detail-url', kwargs={'exh_year': self.exhibition.slug, 'pk': self.id})


class PortfolioAttributes(models.Model):
	""" Аттрибуты фильтра для портфолио """
	Groups = (
		('type', 'тип помещения'),
		('style', 'стиль помещения'),
	)

	group = models.CharField('Группа', choices=Groups, max_length=30)
	name = models.CharField("Название аттрибута", max_length=30)
	slug = models.SlugField('Ярлык', max_length=30, null=True, unique=True)

	class Meta:
		verbose_name = "Аттрибут фильтра"
		verbose_name_plural = "Аттрибуты фильтра"
		db_table = 'filter_attributes'
		ordering = ['group', 'name']

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = uuslug(self.name, instance=self)
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.get_group_display()} / {self.name}"


class PortfolioManager(models.Manager):
	def get_visible_projects(self, user=None, exhibition=None):
		"""Возвращает видимые проекты в зависимости от прав пользователя"""

		today = timezone.now()
		exh_query = models.Q(exhibition=exhibition) if exhibition else models.Q(exhibition__isnull=False)
		queryset = self.get_queryset().filter(
			models.Q(status=True) &
			models.Q(exh_query)
		)

		if exhibition:
			queryset = queryset.select_related('owner').prefetch_related('nominations')

		if not user or not user.is_authenticated:
			# Неавторизованные пользователи видят только проекты завершенных выставок
			return queryset.filter(exhibition__date_end__lt=today)

		from .utils import is_jury_member, get_exhibitor_for_user

		# Staff и жюри видят все проекты
		if user.is_staff or is_jury_member(user):
			return queryset

		# Пытаемся найти участника (exhibitor) для этого пользователя
		exhibitor = get_exhibitor_for_user(user)

		if exhibitor:
			# Владелец видит:
			# 1. Все свои проекты (включая проекты активной выставки)
			# 2. Все чужие проекты, если выставка завершена
			return queryset.filter(
				models.Q(owner=exhibitor) |  # Свои проекты без ограничений
				models.Q(exhibition__date_end__lt=today)  # Проекты завершенных выставок
			)

		# Обычные авторизованные пользователи (не staff, не жюри, не участник)
		return queryset.filter(exhibition__date_end__lt=today)


class Portfolio(BaseImageModel):
	IMAGE_FIELDS = ('cover',)
	CHOICES = (
		(True, 'Доступен'),
		(False, 'Скрыт')
	)

	project_id = models.IntegerField(null=True)
	owner = models.ForeignKey(Exhibitors, on_delete=models.CASCADE, verbose_name='Участник')
	exhibition = models.ForeignKey(
		Exhibitions,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		verbose_name='Выставка',
		help_text='Выберите год, если проект будет участвовать в конкурсе'
	)

	categories = models.ManyToManyField(
		Categories,
		related_name='categories_for_portfolio',
		blank=True,
		verbose_name='Категории',
		help_text='Отметьте нужные категории соответствующие вашему проекту'
	)
	nominations = models.ManyToManyField(
		Nominations,
		related_name='nominations_for_portfolio',
		blank=True,
		verbose_name='Номинации',
		help_text='Отметьте номинации, в которых заявляетесь с Вашим проектом'
	)

	title = models.CharField('Название', max_length=200, blank=True)
	description = RichTextField('Описание портфолио', blank=True)
	cover = models.ImageField(
		'Обложка',
		upload_to=cover_upload_to,
		storage=MediaFileStorage(),
		null=True,
		blank=True,
		validators=[limit_file_size],
		help_text='Размер файла не более %s Мб' % round(settings.FILE_UPLOAD_MAX_MEMORY_SIZE / 1024 / 1024))
	attributes = models.ManyToManyField(
		PortfolioAttributes,
		related_name='attributes_for_portfolio',
		verbose_name='Аттрибуты фильтра',
		blank=True
	)
	status = models.BooleanField('Видимость на сайте', default=True, choices=CHOICES)
	order = models.IntegerField('Порядок', null=True, blank=True, default=1)

	objects = PortfolioManager()

	class Meta:
		ordering = ['-exhibition__slug', 'order', 'title']
		verbose_name = 'Портфолио'
		verbose_name_plural = 'Портфолио работ'
		db_table = 'portfolio'
		unique_together = ['owner', 'project_id']

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.original_cover = self.cover

	def save(self, *args, **kwargs):
		# Сохраняем изображения во временный атрибут для сигнала
		if 'images' in kwargs:
			self._images_to_save = kwargs.pop('images')

		# если файл заменен, то требуется удалить все миниатюры в кэше у sorl-thumbnails
		if self.original_cover and self.original_cover != self.cover:
			delete(self.original_cover)

		if not self.project_id:
			post = Portfolio.objects.filter(owner=self.owner).only('project_id').order_by('project_id').last()
			self.project_id = post.project_id + 1 if post else 1

		super().save(*args, **kwargs)

		self.original_cover = self.cover

	@property
	def get_cover(self):
		"""Возвращает обложку (cover или первое изображение)"""
		if self.cover:
			return self.cover

		# Получаем первое изображение из портфолио
		first_image = self.images.first()
		return first_image.file if first_image else None

	def get_rating_stats(self):
		"""Получение статистики рейтингов"""

		aggregates = self.ratings.aggregate(
			total=models.Sum('star'),
			average=models.Avg('star'),
			count=models.Count('star')
		)

		jury_aggregates = self.ratings.filter(is_jury_rating=True).aggregate(
			jury_total=models.Sum('star'),
			jury_average=models.Avg('star'),
			jury_count=models.Count('star')
		)

		return {
			'total': aggregates['total'] or 0,
			'average': aggregates['average'] or 0.0,
			'count': aggregates['count'] or 0,
			'jury_total': jury_aggregates['jury_total'] or 0,
			'jury_average': jury_aggregates['jury_average'] or 0.0,
			'jury_count': jury_aggregates['jury_count'] or 0,
		}

	def root_comments(self):
		return self.comments_portfolio.filter(parent__isnull=True)

	@property
	def slug(self):
		return 'project-%s' % self.project_id

	def __str__(self):
		if self.title:
			return self.title
		else:
			return 'Проект %s' % self.project_id

	def get_absolute_url(self):
		return reverse(
			'exhibition:project-detail-url',
			kwargs={'owner': self.owner.slug, 'project_id': self.project_id}
		)


class Image(BaseImageModel):
	IMAGE_FIELDS = ('file',)

	portfolio = models.ForeignKey(
		Portfolio,
		on_delete=models.CASCADE,
		null=True,
		related_name='images',
		verbose_name='Портфолио'
	)
	title = models.CharField('Заголовок', max_length=100, null=True, blank=True)
	description = models.CharField('Описание', max_length=250, blank=True)
	file = models.ImageField(
		'Файл',
		upload_to=portfolio_upload_to,
		storage=MediaFileStorage(),
		validators=[limit_file_size],
		help_text=(
				'Можно выбрать несколько фото одновременно. '
				'Размер файла не более %s Мб' % round(settings.FILE_UPLOAD_MAX_MEMORY_SIZE / 1024 / 1024)
		)
	)
	sort = models.SmallIntegerField('Индекс сортировки', blank=True)

	class Meta:
		verbose_name = 'Фото'
		verbose_name_plural = 'Фото проектов'
		ordering = ['sort']
		db_table = 'images'

	def __str__(self):
		if self.title:
			return self.title
		else:
			return self.portfolio.title

	def delete(self, *args, **kwargs):
		# Удаление файла на диске, если файл прикреплен только к текущему портфолио
		if not Image.objects.filter(file=self.file.name).exclude(pk=self.pk).exists():
			# Это последний Image с таким файлом
			delete(self.file)
			folder = path.join(settings.MEDIA_ROOT, path.dirname(self.file.name))
			if not listdir(folder):
				rmdir(folder)

		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		if self.pk:
			img = Image.objects.filter(pk=self.pk).first()
			self.delete_current_file_cache(self.file, current_file=img.file)

		if self.sort is None:
			max_sort = (
					Image.objects
					.filter(portfolio=self.portfolio)
					.aggregate(m=models.Max('sort'))['m'] or 0
			)
			self.sort = max_sort + 1

		super().save(*args, **kwargs)

	def filename(self):
		return self.file.name.rsplit('/', 1)[-1]

	filename.short_description = 'Имя файла'


class Gallery(BaseImageModel):
	""" Exhibition Photo Gallery """
	IMAGE_FIELDS = ('file',)

	exhibition = models.ForeignKey(
		Exhibitions,
		on_delete=models.CASCADE,
		related_name='gallery',
		verbose_name='Выставка'
	)
	title = models.CharField('Заголовок', max_length=100, null=True, blank=True)
	file = models.ImageField(
		'Файл',
		upload_to=gallery_upload_to,
		storage=MediaFileStorage(),
		validators=[limit_file_size],
		help_text=(
				'Можно выбрать несколько фото одновременно. '
				'Размер файла не более %s Мб' % round(settings.FILE_UPLOAD_MAX_MEMORY_SIZE / 1024 / 1024)
		)
	)

	sort = models.SmallIntegerField('Индекс сортировки', blank=True)

	class Meta:
		verbose_name = 'Фото с выставки'
		verbose_name_plural = 'Фото с выставок'
		ordering = ['-exhibition__slug', 'sort']
		db_table = 'gallery'

	def calculate_next_sort_index(self):
		return Gallery.objects.filter(exhibition=self.exhibition).aggregate(m=models.Max('sort'))['m'] or 0

	def delete_storage_file(self):
		try:
			img = Gallery.objects.get(id=self.id)
			self.delete_current_file_cache(self.file, img.file)

		except Gallery.DoesNotExist:
			if path.exists(self.file.path):
				delete(self.file)

	# Удаление файла на диске
	def delete(self, *args, **kwargs):
		delete(self.file)
		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		self.delete_storage_file()

		if self.sort is None:
			sort = self.calculate_next_sort_index()
			self.sort = sort + 1

		super().save(*args, **kwargs)

	def __str__(self):
		if self.title:
			return self.title
		else:
			return self.exhibition.title

	def filename(self):
		return self.file.name.rsplit('/', 1)[-1]

	filename.short_description = 'Имя файла'


class MetaSEO(models.Model):
	model = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name='Раздел')
	post_id = models.PositiveIntegerField('Запись в разделе', null=True, blank=True)
	title = models.CharField('Заголовок страницы', max_length=100, blank=True, null=True)
	description = models.CharField(
		'Мета описание', max_length=100, blank=True, null=True,
		help_text='Описание в поисковой выдаче. Рекомендуется 70-80 символов'
	)
	keywords = models.CharField(
		'Ключевые слова', max_length=255, blank=True, null=True,
		help_text='Поисковые словосочетания указывать через запятую. Рекомендуется до 20 слов и не более 3-х повторов'
	)

	class Meta:
		verbose_name = 'SEO описание'
		verbose_name_plural = 'SEO описания'
		db_table = 'metaseo'
		unique_together = ['model', 'post_id']

	def __str__(self):
		return self.title

	@classmethod
	def get_model(cls, model):
		return ContentType.objects.get(model=model).model_class()

	@staticmethod
	def get_content_models():
		return ContentType.objects.filter(
			model__in=[
				'article', 'portfolio', 'exhibitions', 'categories', 'winners', 'exhibitors', 'partners', 'jury',
				'events'
			]
		)

	@classmethod
	def get_content(cls, model, object_id=None):
		model_name = model.__name__.lower()
		return cls.objects.filter(model__model=model_name, post_id=object_id or None).first()
