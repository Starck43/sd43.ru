from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from blog.models import Article
from rating.admin import RatingInline, ReviewInline
from .exports import ExportExhibitionAdmin
from .forms import (
	ExhibitionsForm, ImageForm, MetaSeoFieldsForm, MetaSeoForm, PortfolioAdminForm, PrepareWinnersForm
)
from .mixins import (
	ProfileAdminMixin, PersonAdminMixin, MediaWidgetMixin, ImagePreviewMixin, ImagesInlineAdminMixin
)
from .models import (
	Categories, Exhibitors, Organizer, Jury, Partners, Events, Nominations, Exhibitions, Winners,
	Portfolio, PortfolioAttributes, Gallery, Image, MetaSEO
)
from .services import delete_cached_fragment, WinnersService

admin.site.unregister(User)  # чтобы снять с регистрации модель User


class ImagesInline(ImagesInlineAdminMixin):
	model = Image

	fields = ('file', 'sort', 'filename')
	verbose_name_plural = 'Фото'


class GalleryInlineAdmin(ImagesInlineAdminMixin):
	model = Gallery
	verbose_name_plural = "Фото с выставки"

	max_num = 30  # Максимум 30 изображений


class EventsInlineAdmin(admin.StackedInline):
	model = Events

	fields = ('title', 'date_event', 'time_start', 'time_end', 'lector',)
	classes = ['events-inline-tab', ]
	verbose_name_plural = "Мероприятия"
	extra = 1


@admin.register(User)
class UserAdmin(BaseUserAdmin):
	prepopulated_fields = {"username": ('email',)}

	# form = CustomSignupForm
	# add_form = CustomSignupForm

	list_display = ('username', 'email', 'first_name', 'last_name', 'date_joined', 'is_active')
	list_filter = ('is_staff', 'is_active', 'groups')
	search_fields = ('username', 'first_name', 'last_name', 'email')
	ordering = ('-id',)

	fieldsets = (
		(None, {'fields': ('username', 'password', 'is_active')}),
		('Персональные данные', {'fields': ('first_name', 'last_name', 'email')}),
		('Права доступа', {'fields': ('is_staff', 'is_superuser', 'groups',)}),
		('Даты', {'fields': ('last_login', 'date_joined')}),
	)

	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('username', 'email', 'password1', 'password2'),
		}),
	)

	def get_fieldsets(self, request, obj=None):
		if not obj:
			return self.add_fieldsets
		return self.fieldsets

	def get_form(self, request, obj=None, **kwargs):
		defaults = {}
		if obj is None:
			defaults['form'] = UserCreationForm
		defaults.update(kwargs)
		return super().get_form(request, obj, **defaults)

	def save_model(self, request, obj, form, change):
		"""Синхронизация User.email → allauth EmailAddress"""

		super().save_model(request, obj, form, change)

		# Если email пустой — удаляем связанные EmailAddress
		if not obj.email:
			EmailAddress.objects.filter(user=obj).delete()
			return

		email = obj.email.strip().lower()

		# Получаем текущий primary email
		existing = EmailAddress.objects.filter(user=obj).first()

		if not existing:
			EmailAddress.objects.create(
				user=obj,
				email=email,
				primary=True,
				verified=True,  # считаем подтвержденным
			)
			return

		updated = False

		if existing.email != email:
			existing.email = email
			updated = True

		if not existing.primary:
			EmailAddress.objects.filter(user=obj).update(primary=False)
			existing.primary = True
			updated = True

		if not existing.verified:
			existing.verified = True
			updated = True

		if updated:
			existing.save()


class MetaSeoFieldsAdmin:
	form = MetaSeoFieldsForm

	meta_fields = ('meta_title', 'meta_description', 'meta_keywords')
	fieldsets = (
		('СЕО Настройки', {
			'classes': ('meta-block',),
			'fields': meta_fields
		}),
	)

	# def get_form(self, request, obj=None, **kwargs):
	# 	form = super().get_form(request, obj, **kwargs)
	# 	return form

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		if obj.pk and not change and form.changed_data:
			MetaSEO.objects.create(
				model=form.meta_model,
				post_id=obj.pk,
				title=form.cleaned_data['meta_title'],
				description=form.cleaned_data['meta_description'],
				keywords=form.cleaned_data['meta_keywords'],
			)


@admin.register(Exhibitors)
class ExhibitorsAdmin(PersonAdminMixin, ProfileAdminMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	ordering = ('name',)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		# Вся логика очистки кэша здесь
		if change and obj.user:
			articles = Article.objects.filter(owner=obj.user)
			if articles:
				delete_cached_fragment('articles')
				for article in articles:
					delete_cached_fragment('article', article.id)

		self.clear_person_cache(obj)


@admin.register(Jury)
class JuryAdmin(PersonAdminMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('persons', 'jury', None)
		exhibitions = Exhibitions.objects.filter(jury=obj.id).only('slug')
		for exh in exhibitions:
			delete_cached_fragment('persons', 'jury', exh.slug)
			delete_cached_fragment('exhibition_content', exh.slug)


@admin.register(Partners)
class PartnersAdmin(PersonAdminMixin, ProfileAdminMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('index_page')
		delete_cached_fragment('persons', 'partners', None)

		exhibitions = Exhibitions.objects.filter(partners=obj).only('slug')
		for exh in exhibitions:
			delete_cached_fragment('persons', 'partners', exh.slug)
			delete_cached_fragment('exhibition_content', exh.slug)


@admin.register(Organizer)
class OrganizerAdmin(PersonAdminMixin, ProfileAdminMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	list_display = ('name', 'description_html',)
	ordering = ('sort',)

	@admin.display(description='Описание для главной страницы', empty_value='')
	def description_html(self, obj):
		return format_html(obj.description)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		delete_cached_fragment('index_page')


@admin.register(Exhibitions)
class ExhibitionsAdmin(ImagePreviewMixin, MediaWidgetMixin, MetaSeoFieldsAdmin, ExportExhibitionAdmin):
	PREVIEW_FIELDS = ('banner',)

	form = ExhibitionsForm
	list_display = ('title', 'date_start', 'date_end',)
	list_display_links = ('title',)
	search_fields = ('title',)
	filter_horizontal = ('nominations', 'jury', 'partners', 'exhibitors',)
	date_hierarchy = 'date_start'
	inlines = [EventsInlineAdmin, GalleryInlineAdmin, ]

	list_per_page = 20
	view_on_site = True

	fieldsets = (
		("Общая информация", {
			'fields': ('title', 'slug', 'banner', 'description', 'date_start', 'date_end', 'location', 'files')
		}),
		("Номинации", {
			'fields': ('nominations',)
		}),
		("Участники", {
			'fields': ('exhibitors',)
		}),
		("Жюри", {
			'fields': ('jury',)
		}),
		("Партнеры", {
			'fields': ('partners',)
		}),
	)

	fieldsets += MetaSeoFieldsAdmin.fieldsets

	def get_search_results(self, request, queryset, search_term):
		queryset, use_distinct = super().get_search_results(
			request, queryset, search_term
		)

		owner_id = request.GET.get('owner')
		if owner_id:
			queryset = queryset.filter(exhibitors__id=owner_id)

		return queryset, use_distinct

	# Отобразим список участников с указанием сортировки по новому полю
	def formfield_for_manytomany(self, db_field, request, **kwargs):
		if db_field.name == "exhibitors":
			kwargs["queryset"] = Exhibitors.objects.order_by('name')
		return super().formfield_for_manytomany(db_field, request, **kwargs)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		# сохраним связанные с выставкой фото
		images = request.FILES.getlist('files')
		for image in images:
			# upload_filename = path.join('gallery/', obj.slug, image.name)
			# file_path = path.join(settings.MEDIA_ROOT, upload_filename)
			instance = Gallery(exhibition=obj, file=image)
			instance.save()

		delete_cached_fragment('navbar')
		delete_cached_fragment('exhibition_banner', obj.slug)
		delete_cached_fragment('exhibition_content', obj.slug)
		delete_cached_fragment('exhibition_events', obj.slug)
		delete_cached_fragment('exhibition_gallery', obj.slug)
		delete_cached_fragment('exhibition_overlay', obj.slug)
		if not change:
			delete_cached_fragment('exhibitions_list')


@admin.register(Categories)
class CategoriesAdmin(ImagePreviewMixin, MediaWidgetMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('logo',)

	list_display = ('title', 'nominations_list', 'description')
	list_display_links = ('title',)

	fieldsets = (
		(None, {
			'fields': ('title', 'slug', 'description', 'logo', 'sort')
		}),
	)

	fieldsets += MetaSeoFieldsAdmin.fieldsets

	@admin.display(description='Номинации', empty_value='')
	def nominations_list(self, obj):
		return ', '.join(obj.nominations_set.all().values_list('title', flat=True))

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('categories_list')


@admin.register(Nominations)
class NominationsAdmin(MetaSeoFieldsAdmin, admin.ModelAdmin):
	fieldsets = (
		(None, {
			'classes': ('user-block',),
			'fields': ('category', 'title', 'slug', 'description', 'sort',),
		}),
	)
	fieldsets += MetaSeoFieldsAdmin.fieldsets

	list_display = ('title', 'category', 'description_html',)
	list_display_links = ('title',)

	list_per_page = 20
	empty_value_display = '<пусто>'

	@admin.display(description='Описание', empty_value='')
	def description_html(self, obj):
		return format_html(obj.description)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		portfolio = Portfolio.objects.filter(nominations=obj)
		for item in portfolio:
			delete_cached_fragment('portfolio_list', item.owner.slug, item.project_id, True)
			delete_cached_fragment('portfolio_list', item.owner.slug, item.project_id, False)


@admin.register(Winners)
class WinnersAdmin(MetaSeoFieldsAdmin, admin.ModelAdmin):
	fieldsets = (
		(None, {
			'classes': ('user-block',),
			'fields': ('exhibition', 'nomination', 'exhibitor', 'portfolio',),
		}),
	)
	fieldsets += MetaSeoFieldsAdmin.fieldsets

	list_display = ('get_exhibition', 'exhibitor', 'nomination', 'portfolio')
	list_display_links = ('get_exhibition', 'exhibitor',)
	# search_fields = ('nomination__title', 'exhibitor__name',)
	list_filter = ('exhibition__date_start', 'nomination', 'exhibitor')
	date_hierarchy = 'exhibition__date_start'
	ordering = ('-exhibition__date_start',)

	change_list_template = 'admin/exhibition/winners/change_list.html'

	list_per_page = 20
	save_as = True
	save_on_top = True  # adding the Save button on top bar

	@admin.display(
		description='Название выставки',
		empty_value='<Вневыставочный проект>',
		ordering='exhibition'
	)
	def get_exhibition(self, obj):
		if obj.exhibition:
			return obj.exhibition

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "exhibitor":
			kwargs["queryset"] = Exhibitors.objects.order_by('name')

		return super().formfield_for_foreignkey(db_field, request, **kwargs)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('persons', 'winners', None)
		exhibitions = Exhibitions.objects.all()
		for exh in exhibitions:
			delete_cached_fragment('persons', 'winners', exh.slug)

		delete_cached_fragment('exhibition_content', obj.exhibition.slug)
		delete_cached_fragment('participant_detail', obj.portfolio.id)

	def get_urls(self):
		urls = super().get_urls()
		custom = [
			path(
				'prepare/',
				self.admin_site.admin_view(self.prepare_winners),
				name='exhibition_winners_prepare'
			),
			path(
				'confirm/',
				self.admin_site.admin_view(self.confirm_winners),
				name='exhibition_winners_confirm'
			),
		]
		return custom + urls

	def prepare_winners(self, request):
		form = PrepareWinnersForm(request.POST or None)

		if request.method == 'POST' and form.is_valid():
			exhibition = form.cleaned_data['exhibition']

			exhibition = Exhibitions.objects.prefetch_related(
				'exhibition_for_winner'
			).get(id=exhibition.id)

			preview = WinnersService.build_winners_preview(exhibition)

			if not preview['conflicts']:
				WinnersService.save_winners(preview)
				self.message_user(request, 'Победители успешно сформированы')
				return redirect('..')

			request.session['winners_preview'] = WinnersService.serialize_preview(preview)
			# Правильный формат имени для admin URL
			return redirect('admin:exhibition_winners_confirm')

		context = {
			**self.admin_site.each_context(request),
			'title': 'Формирование победителей',
			'form': form,
		}
		return render(request, 'admin/exhibition/winners/prepare.html', context)

	def confirm_winners(self, request):
		preview_data = request.session.get('winners_preview')
		if not preview_data:
			self.message_user(request, 'Нет данных для подтверждения', level='warning')
			return redirect('..')

		preview = WinnersService.deserialize_preview(preview_data)
		warning_message = None

		if request.method == 'GET':
			exhibition = preview['exhibition']
			winners_count = exhibition.exhibition_for_winner.count()
			if winners_count:
				warning_message = (
					f'ВНИМАНИЕ: Для выставки "{exhibition.title}" уже есть победители! Всего: {winners_count}. '
					f'При сохранении они будут перезаписаны.'
				)

			# Простая статистика
			total_nominations = len(preview['items'])
			nominations_with_winners = sum(1 for item in preview['items'] if item.get('winners'))
			nominations_incomplete = sum(1 for item in preview['items']
			                             if item.get('incomplete') or item.get('no_participants') or item.get(
				'no_qualified_votes'))

			stats = {
				'total_nominations': total_nominations,
				'nominations_with_winners': nominations_with_winners,
				'nominations_incomplete': nominations_incomplete,
				'nominations_conflicted': len(preview['conflicts']),
			}

		else:
			# POST - сохраняем с ручным выбором
			manual_selection = {
				key.replace('nomination_', ''): value
				for key, value in request.POST.items()
				if key.startswith('nomination_')
			}

			try:
				WinnersService.save_winners(preview, manual_selection)
				if 'winners_preview' in request.session:
					del request.session['winners_preview']
				self.message_user(request, 'Победители успешно сохранены')
			except Exception as e:
				self.message_user(request, f'Ошибка: {str(e)}', level='error')

			return redirect('..')

		context = {
			**self.admin_site.each_context(request),
			'title': 'Подтверждение победителей',
			'preview': preview,
			'stats': stats,
			'warning_message': warning_message,
			'conflicts_dict': {c['nomination'].id: c for c in preview['conflicts']},  # для быстрого поиска
		}
		return render(request, 'admin/exhibition/winners/confirm.html', context)


@admin.register(Events)
class EventsAdmin(MetaSeoFieldsAdmin, admin.ModelAdmin):
	fieldsets = (
		(None, {
			'classes': ('user-block',),
			'fields': (
				'exhibition', 'title', 'date_event', 'time_start', 'time_end', 'location', 'hoster',
				'lector', 'description',
			),
		}),
	)
	fieldsets += MetaSeoFieldsAdmin.fieldsets

	list_display = ('title', 'date_event', 'time_event', 'hoster', 'exhibition',)
	list_filter = ('exhibition__date_start', 'date_event',)
	date_hierarchy = 'exhibition__date_start'
	search_fields = ('title', 'description', 'hoster', 'lector',)
	ordering = ('-exhibition__slug', 'date_event', 'time_start',)

	list_per_page = 20
	save_as = True

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('exhibition_events', obj.exhibition.slug)


@admin.register(Portfolio)
class PortfolioAdmin(ImagePreviewMixin, MediaWidgetMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('cover',)

	form = PortfolioAdminForm

	list_display = ('id', 'title', 'exhibition', 'owner', 'nominations_list', 'status_field')
	list_display_links = ('id', 'title')
	list_filter = ('nominations', 'owner', 'status')
	search_fields = (
		'title', 'owner__name', 'owner__user__first_name', 'owner__user__last_name', 'exhibition__title',
		'nominations__title'
	)
	ordering = ('-id',)

	date_hierarchy = 'exhibition__date_start'
	# autocomplete_fields = ('owner', 'exhibition')

	fieldsets = (
		('Основная информация', {
			'classes': ('portfolio-block',),
			'fields': (
				'owner', 'exhibition', 'categories', 'nominations',
				'title', 'description', 'cover', 'files',
				'attributes', 'status', 'order'
			),
		}),
	)
	fieldsets += MetaSeoFieldsAdmin.fieldsets

	jazzmin_section_order = ("Основная информация", "Фото", "Оценки проекта", "Отзывы", "СЕО Настройки",)

	save_on_top = True
	save_as = True
	view_on_site = True
	list_per_page = 50

	inlines = [ImagesInline, RatingInline, ReviewInline]

	class Media:
		js = (
			# 'admin/js/vendor/jquery/jquery.js',
			# 'admin/js/portfolio_admin.js',
		)

	@admin.display(description='Номинации', ordering="nominations__title", empty_value='')
	def nominations_list(self, obj):
		"""Отображение списка номинаций в админке"""
		if obj.nominations.exists():
			return ', '.join(obj.nominations.values_list('title', flat=True))
		return 'Нет номинаций'

	@admin.display(description='Видимость', boolean=True, ordering="status")
	def status_field(self, obj):
		return obj.status

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "owner":
			kwargs["queryset"] = Exhibitors.objects.order_by('name')

		if db_field.name == "exhibition":
			kwargs["queryset"] = Exhibitions.objects.order_by('-date_start')

		return super().formfield_for_foreignkey(db_field, request, **kwargs)

	def save_related(self, request, form, formsets, change):
		super().save_related(request, form, formsets, change)

		order = request.POST.get('images_order')
		if not order:
			return

		ids = [int(pk) for pk in order.split(',') if pk.isdigit()]

		images = Image.objects.in_bulk(ids)

		for index, image_id in enumerate(ids, start=1):
			img = images.get(image_id)
			if img:
				img.sort = index

		Image.objects.bulk_update(images.values(), ['sort'])

	def save_model(self, request, obj, form, change):
		images = request.FILES.getlist('files')
		obj.save(images=images)  # сохраним портфолио и связанные фотографии


@admin.register(Gallery)
class GalleryAdmin(ImagePreviewMixin, MediaWidgetMixin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('file',)

	fields = ('exhibition', 'title', 'file', 'sort')
	list_display = ('exhibition', 'title',)
	list_display_links = list_display
	search_fields = ('title', 'exhibition__title', 'exhibition__slug',)
	list_filter = ('exhibition__date_start',)
	date_hierarchy = 'exhibition__date_start'

	save_on_top = True
	list_per_page = 30

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('exhibition_overlay', obj.exhibition.slug)
		delete_cached_fragment('exhibition_gallery', obj.exhibition.slug)


@admin.register(Image)
class ImageAdmin(ImagePreviewMixin, MediaWidgetMixin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('file',)

	form = ImageForm
	fields = ('portfolio', 'title', 'description', 'file', 'sort')
	list_display = ('portfolio', 'title', 'author', 'sort',)
	list_display_links = ('portfolio', 'title',)
	list_filter = ('portfolio__owner', 'portfolio',)
	search_fields = (
		'title', 'file', 'portfolio__title', 'portfolio__owner__slug', 'portfolio__owner__name',
		'portfolio__owner__user__first_name', 'portfolio__owner__user__last_name',
	)

	list_per_page = 50

	# def save_model(self, request, obj, form, change):
	# 	obj.save()
	# 	for image in request.FILES.getlist('images'):
	# 		obj.create(image=image)

	@admin.display(description='Автор', empty_value='')
	def author(self, obj):
		author = None
		if obj.portfolio:
			author = obj.portfolio.owner
		return author


@admin.register(PortfolioAttributes)
class PortfolioAttributesAdmin(admin.ModelAdmin):
	prepopulated_fields = {"slug": ('name',)}
	search_fields = ('name',)
	list_per_page = 20

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		for category in Categories.objects.all():
			delete_cached_fragment('sidebar', category.slug)


@admin.register(MetaSEO)
class MetaAdmin(admin.ModelAdmin):
	form = MetaSeoForm
	list_display = ('model', 'root', 'title', 'description')
	list_display_links = ('model', 'title',)
	ordering = ('model', '-post_id')
	search_fields = ('title', 'description', 'model__app_label')

	# добавим кастомный название в админке
	# заменим название модели в ContentType
	def get_name(self):
		verbose_name = self.model_class()._meta.verbose_name_plural
		return verbose_name if verbose_name else self.__str__()

	ContentType.add_to_class('__str__', get_name)

	def root(self, obj):
		if obj.post_id:
			model = MetaSEO.get_model(obj.model.model)
			post = model.objects.get(pk=obj.post_id)
		else:
			post = None
		return post

	root.short_description = 'Запись'
