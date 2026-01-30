import re
from datetime import timedelta
from os import path, rename, rmdir, listdir

from ckeditor.fields import RichTextField
from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.contrib.auth.models import User, UserManager
from django.contrib.contenttypes.models import ContentType
from django.core.validators import RegexValidator
from django.db.models import F
from django.db.models.functions import Coalesce
# from django.utils.text import slugify
from django.urls import reverse  # Used to generate URLs by reversing the URL patterns
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from smart_selects.db_fields import ChainedForeignKey, ChainedManyToManyField
# from django.core.files.base import ContentFile
from sorl.thumbnail import delete
from uuslug import uuslug

from crm import models
from crm.validators import svg_validator
from .base_models import UserModel
from .fields import SVGField
from .logic import (
	MediaFileStorage, get_image_html, image_resize, portfolio_upload_to, cover_upload_to, gallery_upload_to,
	limit_file_size, update_google_sitemap
)

LOGO_FOLDER = 'logos/'
BANNER_FOLDER = 'banners/'


class Person(UserModel, models.Model):
	""" Abstract model for Exhibitors, Organizer, Jury, Partners """
	logo = models.ImageField('Логотип', upload_to=LOGO_FOLDER, storage=MediaFileStorage(), null=True, blank=True)
	name = models.CharField('Имя контакта', max_length=100)
	slug = models.SlugField('Ярлык', max_length=100, unique=True)
	description = RichTextUploadingField('Информация о контакте', blank=True)
	sort = models.IntegerField('Индекс сортировки', null=True, blank=True)

	class Meta:
		abstract = True  # Table will not be created

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)

		# Извлекаем request из kwargs если он там есть
		request = None
		for arg in args:
			if hasattr(arg, 'META'):  # Это request
				request = arg
				break

		# Первый save() - инициализируем оригинальные значения
		if not hasattr(self, 'original_logo'):
			self.original_logo = None
		if not hasattr(self, 'original_slug'):
			self.original_slug = None

		# Если это новый объект (еще нет id), устанавливаем значения
		if self.pk is None:
			self.original_logo = self.logo
			self.original_slug = self.slug

		if not self.slug:
			self.slug = uuslug(self.name.lower(), instance=self)

		# если файл заменен, то требуется удалить все миниатюры в кэше у sorl-thumbnails
		if self.original_logo and self.original_logo != self.logo:
			delete(self.original_logo)

		if request and 'logo' in request.FILES:
			resized_logo = image_resize(self.logo, [450, 450], uploaded_file=request.FILES.get('logo'))
			if resized_logo and resized_logo != 'error':
				self.logo = resized_logo

		if self.original_slug and self.slug != self.original_slug:
			self.handle_slug_change()
			self.original_slug = self.slug

		super(Person, self).save(*args, **kwargs)
		self.original_logo = self.logo

	def handle_slug_change(self):
		"""Обработка изменения slug. Переопределяется в дочерних классах при необходимости."""

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
				renamed_file = str(image.file).replace(self.original_slug, self.slug)
				image.file = renamed_file
				image.save()

	def logo_thumb(self):
		return get_image_html(self.logo)

	logo_thumb.short_description = 'Логотип'


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
	objects = UserManager()

	class Meta(Person.Meta):
		verbose_name = 'Участник выставки'
		verbose_name_plural = 'Участники'
		ordering = ['user__last_name']
		db_table = 'exhibitors'
		unique_together = ['user', ]

	def get_absolute_url(self):
		return reverse('exhibition:exhibitor-detail-url', kwargs={'slug': self.slug})


class Organizer(Person, Profile):
	objects = UserManager()

	# Metadata
	class Meta(Person.Meta):
		verbose_name = 'Организатор'
		verbose_name_plural = 'Организаторы'
		db_table = 'organizers'
		ordering = ['sort', 'name']


class Jury(Person):
	excerpt = models.CharField('Краткое описание', max_length=255, null=True, blank=True)

	objects = UserManager()

	class Meta(Person.Meta):
		verbose_name = 'Жюри'
		verbose_name_plural = 'Жюри'
		ordering = ['sort', 'name']
		db_table = 'jury'

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()  # обновим карту сайта Google

	def get_absolute_url(self):
		return reverse('exhibition:jury-detail-url', kwargs={'slug': self.slug})


class Partners(Person, Profile):
	objects = UserManager()

	class Meta(Person.Meta):
		verbose_name = 'Партнер выставки'
		verbose_name_plural = 'Партнеры'
		db_table = 'partners'
		ordering = [Coalesce("sort", F('id') + 500)]  # сортировка в приоритете по полю sort, а потом уже по-умолчанию

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()  # обновим карту сайта Google

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

	def logo_thumb(self):
		"""Маленькое превью для списка в админке"""
		return get_image_html(self.logo, width=50, height=50, css_class='admin-thumb')

	logo_thumb.short_description = 'Логотип'
	logo_thumb.allow_tags = True

	def get_absolute_url(self):
		return reverse('exhibition:projects-list-url', kwargs={'slug': self.slug})


class Nominations(models.Model):
	""" Таблица Номинаций """
	category = models.ForeignKey(Categories, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Категория')
	title = models.CharField('Номинация', max_length=150)
	slug = models.SlugField('Ярлык', max_length=150, unique=True)
	description = RichTextUploadingField('Описание номинации', blank=True)
	sort = models.IntegerField('Индекс сортировки', null=True, blank=True)

	# Metadata
	class Meta:
		ordering = ['sort', 'title']  # '-' for DESC ordering
		verbose_name = 'Номинация'
		verbose_name_plural = 'Номинации'
		db_table = 'nominations'

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = uuslug(self.title.lower(), instance=self)
		super().save(*args, **kwargs)
		update_google_sitemap()  # обновим карту сайта Google

	def __str__(self):
		return self.title

	def get_absolute_url(self):
		if self.category:
			return reverse('exhibition:projects-list-url', kwargs={'slug': self.category.slug})
		else:
			return reverse('exhibition:category-list-url', kwargs={'slug': None})


class Exhibitions(models.Model):
	""" Таблица Выставки """
	title = models.CharField('Название выставки', max_length=150)
	slug = models.SlugField('Ярлык', max_length=150, unique=True)
	banner = models.ImageField('Баннер', upload_to=BANNER_FOLDER, null=True, blank=True)
	description = RichTextUploadingField('Описание выставки', blank=True)
	date_start = models.DateField('Начало выставки', unique=True)
	date_end = models.DateField('Окончание выставки', unique=True)
	location = models.CharField('Расположение выставки', max_length=200, blank=True)
	exhibitors = models.ManyToManyField(
		Exhibitors, related_name='exhibitors_for_exh', verbose_name='Участники', blank=True
	)
	partners = models.ManyToManyField(Partners, related_name='partners_for_exh', verbose_name='Партнеры', blank=True)
	jury = models.ManyToManyField(Jury, related_name='jury_for_exh', verbose_name='Жюри', blank=True)
	nominations = models.ManyToManyField(
		Nominations,
		related_name='nominations_for_exh',
		verbose_name='Номинации',
		blank=True
	)

	# events = models.ManyToManyField(Events, related_name='events_for_exh', verbose_name = 'Мероприятия')

	# Metadata
	class Meta:
		ordering = ['-date_start']  # '-' for DESC ordering
		verbose_name = 'Выставка'
		verbose_name_plural = 'Выставки'
		db_table = 'exhibitions'

	# удаление связанных фото с галереей
	def delete(self, *args, **kwargs):
		posts = self.gallery.all()
		for post in posts:
			post.delete()

		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = uuslug(self.date_start.strftime('%Y'), instance=self)
		super().save(*args, **kwargs)
		update_google_sitemap()  # обновим карту сайта Google

	def __str__(self):
		return self.title

	@property
	def status(self):
		from django.utils.timezone import now

		today = now().date()
		return 'upcoming' if today < self.date_start else 'active' if today <= self.date_end else 'finished'

	@property
	def rating_deadline(self):
		"""Дедлайн для обычных пользователей (после выставки)"""
		return self.date_end - timedelta(days=1)

	@property
	def jury_deadline(self):
		"""Дедлайн для жюри (до начала выставки)"""
		return self.date_start

	@property
	def is_jury_voting_active(self):
		"""Активно ли голосование жюри (до начала выставки)"""
		today = now().date()
		return today < self.jury_deadline

	@property
	def is_exhibition_ended(self):
		"""Завершилась ли выставка для обычных пользователей"""
		today = now().date()
		return today > self.rating_deadline

	def exh_year(self):
		return self.date_start.strftime('%Y')

	exh_year.short_description = 'Выставка'

	def banner_thumb(self):
		return get_image_html(self.banner)

	banner_thumb.short_description = 'Логотип'

	def get_absolute_url(self):
		return reverse('exhibition:exhibition-detail-url', kwargs={'exh_year': self.slug})


class Winners(models.Model):
	""" Таблица Победителей """
	exhibition = models.ForeignKey(
		Exhibitions, related_name='exhibition_for_winner', on_delete=models.CASCADE,
		null=True, verbose_name='Выставка'
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
		ordering = ['-exhibition__slug']
		verbose_name = 'Победитель выставки'
		verbose_name_plural = 'Победители'
		db_table = 'winners'
		unique_together = ['exhibition', 'exhibitor', 'nomination']

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()  # обновим карту сайта Google

	def __str__(self):
		return '%s | %s, %s' % (self.exhibitor.name, self.nomination.title, self.exhibition.slug)

	def exh_year(self):
		# return only Exhibition's year from date_start
		return self.exhibition.date_start.strftime('%Y')

	exh_year.short_description = 'Выставка'

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
		null=True,
		blank=True,
		verbose_name='Выставка'
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
		ordering = ['date_event', 'time_start']  # '-' for DESC ordering
		verbose_name = 'Мероприятие'
		verbose_name_plural = 'Мероприятия'
		db_table = 'events'

	# unique_together = ['date_event', 'time_start', 'time_end']

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		update_google_sitemap()  # обновим карту сайта Google

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
	def get_queryset(self):
		return super().get_queryset().filter(status=True)

	def get_visible_projects(self, user=None):
		"""Возвращает видимые проекты в зависимости от прав пользователя"""
		queryset = self.get_queryset().filter(exhibition__isnull=False)
		today = now().date()

		if not user or not user.is_authenticated:
			# Неавторизованные пользователи видят только:
			# - проекты без выставки
			# - проекты с начавшейся или завершенной выставкой
			return queryset.filter(exhibition__date_start__lte=today)

		# Staff и жюри видят все проекты
		from .utils import is_jury_member, get_exhibitor_for_user

		if user.is_staff or is_jury_member(user):
			return queryset

		# Пытаемся найти участника (exhibitor) для этого пользователя
		exhibitor = get_exhibitor_for_user(user)

		if exhibitor:
			# Владелец видит:
			# 1. Все свои проекты (даже с upcoming выставками)
			# 2. Проекты других участников, которые доступны всем
			return queryset.filter(
				models.Q(owner=exhibitor) |  # Свои проекты без ограничений
				models.Q(exhibition__date_start__lte=today)  # Проекты с начавшейся/завершенной выставкой
			)

		# Обычные авторизованные пользователи (не staff, не жюри, не участник)
		return queryset.filter(exhibition__date_start__lte=today)


class Portfolio(models.Model):
	project_id = models.IntegerField(null=True)
	owner = models.ForeignKey(Exhibitors, on_delete=models.CASCADE, verbose_name='Участник')
	exhibition = models.ForeignKey(
		Exhibitions,
		on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Выставка',
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
	order = models.IntegerField('Порядок', null=True, blank=True, default=1)
	status = models.BooleanField('Статус', null=True, blank=True, default=True, help_text='Видимость на сайте')

	objects = PortfolioManager()

	# Metadata
	class Meta:
		ordering = ['-exhibition__slug', 'order', 'title']
		verbose_name = 'Портфолио'
		verbose_name_plural = 'Портфолио работ'
		db_table = 'portfolio'
		unique_together = ['owner', 'project_id']

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.original_cover = self.cover

	def delete(self, *args, **kwargs):
		# удаление связанных фото с портфолио
		for post in self.images.all():
			post.delete()

		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		# если файл заменен, то требуется удалить все миниатюры в кэше у sorl-thumbnails
		if self.original_cover and self.original_cover != self.cover:
			delete(self.original_cover)

		resized_cover = image_resize(self.cover, [1500, 900])
		if resized_cover and resized_cover != 'error':
			self.cover = resized_cover

		images = kwargs.pop('images', [])

		if not self.project_id:
			# найдем последнюю запись с наибольшим id
			post = Portfolio.objects.filter(owner=self.owner).only('project_id').order_by('project_id').last()
			if post:
				self.project_id = post.project_id + 1
			else:
				self.project_id = 1

		super().save(*args, **kwargs)

		if resized_cover != 'error':
			self.original_cover = self.cover

		# сохраним связанные с портфолио изображения
		if self.pk and images:
			for image in images:
				exhibition_slug = self.exhibition.slug if self.exhibition else 'non-exhibition'
				upload_filename = path.join(
					settings.MEDIA_ROOT,
					settings.FILES_UPLOAD_FOLDER,
					self.owner.slug,
					exhibition_slug,
					self.slug,
					image.name
				)
				append_image = True

				if path.exists(upload_filename):
					try:
						# Portfolio has an image yet
						exist_image = Image.objects.get(portfolio=self, file=upload_filename)
						# Проверим размер загруженного повторно файла и изменим оригинал, если он превысит лимит указанный в settings
						image_resize(exist_image.file)
						append_image = False
					except Image.DoesNotExist:
						# New image in portfolio
						image = upload_filename

				if append_image:
					instance = Image(portfolio=self, file=image)
					instance.save()

	@property
	def slug(self):
		return 'project-%s' % self.project_id

	def get_rating_stats(self):
		"""Получение статистики рейтингов в виде словаря"""

		aggregates = self.ratings.aggregate(
			total=models.Sum('star'),
			average=models.Avg('star'),
			count=models.Count('star')
		)

		jury_aggregates = self.ratings.filter(is_jury_rating=True).aggregate(
			jury_average=models.Avg('star'),
			jury_count=models.Count('star')
		)

		return {
			'total': aggregates.get('total') or 0,
			'average': aggregates.get('average') or 0.0,
			'count': aggregates.get('count') or 0,
			'jury_average': jury_aggregates.get('jury_average') or 0.0,
			'jury_count': jury_aggregates.get('jury_count') or 0
		}

	def root_comments(self):
		return self.comments_portfolio.filter(parent__isnull=True)

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


class Gallery(models.Model):
	""" Exhibition Photo Gallery """

	exhibition = models.ForeignKey(
		Exhibitions, on_delete=models.CASCADE, related_name='gallery',
		verbose_name='Выставка'
	)
	title = models.CharField('Заголовок', max_length=100, null=True, blank=True)
	file = models.ImageField('Фото', upload_to=gallery_upload_to)

	# Metadata
	class Meta:
		verbose_name = 'Фото с выставки'
		verbose_name_plural = 'Фото с выставки'
		db_table = 'gallery'

	def delete_storage_file(self):
		try:
			# is the object in the database yet?
			obj = Gallery.objects.get(id=self.id)
			if obj.file and self.file and obj.file != self.file:
				delete(obj.file)
		except Gallery.DoesNotExist:
			if path.exists(self.file.path):
				delete(self.file)

	# Удаление файла на диске
	def delete(self, *args, **kwargs):
		delete(self.file)
		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		self.delete_storage_file()
		resized_image = image_resize(self.file)
		if resized_image:
			self.file = resized_image
		super().save(*args, **kwargs)

	def __str__(self):
		if self.title:
			return self.title
		else:
			return '<Без имени>'

	def file_thumb(self):
		return get_image_html(self.file)

	file_thumb.short_description = 'Фото'

	def filename(self):
		return self.file.name.rsplit('/', 1)[-1]

	filename.short_description = 'Имя файла'


class Image(models.Model):
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
	sort = models.SmallIntegerField('Индекс сортировки')

	class Meta:
		verbose_name = 'Фото'
		verbose_name_plural = 'Фото проектов'
		ordering = ['sort']
		db_table = 'images'

	def __str__(self):
		if self.title:
			return self.title
		else:
			return '<Без имени>'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.original_file = self.file

	def delete(self, *args, **kwargs):
		# Удаление файла на диске, если файл прикреплен только к текущему портфолио
		if len(Image.objects.filter(file=self.file.name)) == 1:
			# физически удалим файл с диска, если он единственный
			delete(self.file)
			folder = path.join(settings.MEDIA_ROOT, path.dirname(self.file.name))
			if not listdir(folder):
				rmdir(folder)

		super().delete(*args, **kwargs)

	def save(self, *args, **kwargs):
		if self.sort is None:
			max_sort = (
					Image.objects
					.filter(portfolio=self.portfolio)
					.aggregate(m=models.Max('sort'))['m'] or 0
			)
			self.sort = max_sort + 1

		# если файл заменен, то требуется удалить все миниатюры в кэше у sorl-thumbnails
		if self.original_file and self.original_file != self.file:
			delete(self.original_file)

		# Resizing uploading image
		# Alternative package - django-resized
		resized_image = image_resize(self.file)
		if resized_image and resized_image != 'error':
			self.file = resized_image

		if resized_image != 'error':
			super().save(*args, **kwargs)
			self.original_file = self.file

	def file_thumb(self):
		return get_image_html(self.file)

	file_thumb.short_description = 'Фото'

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

	# Metadata
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
