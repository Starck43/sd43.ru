from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import ImageField
from django.utils.html import format_html
from sorl.thumbnail.admin import AdminImageMixin

from blog.models import Article
from rating.admin import RatingInline, ReviewInline
from .forms import (
	ExhibitionsForm, ImageForm, MetaSeoFieldsForm, MetaSeoForm, CustomClearableFileInput, PortfolioAdminForm
)
from .logic import delete_cached_fragment
from .mixins import ProfileAdminMixin, PersonAdminMixin, MediaWidgetMixin
from .models import (
	Categories, Exhibitors, Organizer, Jury, Partners, Events, Nominations, Exhibitions, Winners,
	Portfolio, PortfolioAttributes, Gallery, Image, MetaSEO
)


admin.site.unregister(User)  # чтобы снять с регистрации модель User


class ImagesInline(admin.StackedInline):
	model = Image
	extra = 1
	template = 'admin/exhibition/edit_inline/stacked_images.html'
	show_change_link = True
	fields = ('file_thumb', 'file', 'title', 'sort', 'filename',)
	list_display = ('file_thumb', 'title',)
	readonly_fields = ('file_thumb', 'filename',)
	list_editable = ['title', 'sort']

	class Media:
		css = {
			'all': (
				'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
				'admin/css/portfolio-images.min.css',
			)
		}
		js = (
			# 'admin/js/vendor/jquery/jquery.js',
			'admin/js/portfolio-images.min.js',
		)


class GalleryInlineAdmin(admin.StackedInline):
	model = Gallery
	template = 'admin/exhibition/edit_inline/stacked.html'
	extra = 1  # new blank record count
	show_change_link = True
	fields = ('file_thumb', 'file', 'title', 'filename',)
	list_display = ('file_thumb', 'title',)
	readonly_fields = ('file_thumb', 'filename',)
	list_editable = ['title']
	classes = ['gallery-inline-tab', ]
	verbose_name_plural = "Загруженные фотографии"
	list_per_page = 30

	formfield_overrides = {
		ImageField: {'widget': CustomClearableFileInput()},
	}


class EventsInlineAdmin(admin.StackedInline):
	model = Events
	extra = 1  # new blank record count
	fields = ('title', 'date_event', 'time_start', 'time_end', 'lector',)
	classes = ['events-inline-tab', ]
	verbose_name_plural = "Мероприятия"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
	prepopulated_fields = {"username": ('email',)}

	# form = CustomSignupForm
	# add_form = CustomSignupForm

	list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
	list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
	search_fields = ('username', 'first_name', 'last_name', 'email')
	ordering = ('username',)

	fieldsets = (
		(None, {'fields': ('username', 'password')}),
		('Персональные данные', {'fields': ('first_name', 'last_name', 'email')}),
		('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups',)}),
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

		delete_cached_fragment('persons', 'exhibitors', None)

		if obj.id:
			exhibitions = Exhibitions.objects.filter(exhibitors=obj.id).only('slug')
			for exh in exhibitions:
				delete_cached_fragment('persons', 'exhibitors', exh.slug)
				delete_cached_fragment('exhibition_content', exh.slug)


@admin.register(Jury)
class JuryAdmin(PersonAdminMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('persons', 'jury', None)
		exhibitions = Exhibitions.objects.filter(jury=obj.id).only('slug')
		for exh in exhibitions:
			delete_cached_fragment('persons', 'jury', exh.slug)
			delete_cached_fragment('exhibition_content', exh.slug)


@admin.register(Organizer)
class OrganizerAdmin(PersonAdminMixin, ProfileAdminMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	list_display = ('logo_thumb', 'name', 'description_html',)
	ordering = ('sort',)

	@admin.display(description='Описание для главной страницы', empty_value='')
	def description_html(self, obj):
		return format_html(obj.description)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		delete_cached_fragment('index_page')


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


@admin.register(Exhibitions)
class ExhibitionsAdmin(MediaWidgetMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	form = ExhibitionsForm
	list_display = ('title', 'date_start', 'date_end',)
	list_display_links = ('title',)
	search_fields = ('title',)
	date_hierarchy = 'date_start'
	filter_horizontal = ('nominations', 'exhibitors',)
	# list_select_related = ('events',)
	# prepopulated_fields = {"slug": ('date_start',)} # adding name to slug field but not only DateFields
	list_per_page = 20
	view_on_site = True
	inlines = [EventsInlineAdmin, GalleryInlineAdmin, ]

	fieldsets = (
		("Общая информация", {
			'fields': ('title', 'slug', 'banner', 'description', 'date_start', 'date_end', 'location',)
		}),
		("Участники", {
			'fields': ('exhibitors',)
		}),
		("Номинации", {
			'fields': ('nominations',)
		}),
		("Жюри", {
			'fields': ('jury',)
		}),
		("Партнеры", {
			'fields': ('partners',)
		}),
		("Фото с выставки", {
			'fields': ('files',)
		}),
		("СЕО Настройки", {
			'fields': MetaSeoFieldsAdmin.meta_fields
		}),
	)
	filter_horizontal = ('nominations', 'jury', 'partners', 'exhibitors',)

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

	# def formfield_for_foreignkey(self, db_field, request, **kwargs):
	# 	return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
class CategoriesAdmin(MediaWidgetMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	list_display = ('logo_thumb', 'title', 'nominations_list', 'description')
	list_display_links = ('logo_thumb', 'title')

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

	list_display = ('category', 'title', 'description_html',)
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
	search_fields = ('title', 'description', 'hoster', 'lector',)
	list_filter = ('exhibition__date_start', 'date_event',)
	date_hierarchy = 'exhibition__date_start'
	list_per_page = 20
	save_as = True
	ordering = ('-exhibition__slug', 'date_event', 'time_start',)

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('exhibition_events', obj.exhibition.slug)


@admin.register(Winners)
class WinnersAdmin(MetaSeoFieldsAdmin, admin.ModelAdmin):
	fieldsets = (
		(None, {
			'classes': ('user-block',),
			'fields': ('exhibition', 'nomination', 'exhibitor', 'portfolio',),
		}),
	)
	fieldsets += MetaSeoFieldsAdmin.fieldsets

	list_display = ('exhibitor', 'exh_year', 'nomination', 'portfolio')
	list_display_links = ('exhibitor',)
	# search_fields = ('nomination__title', 'exhibitor__name',)
	list_filter = ('exhibition__date_start', 'nomination', 'exhibitor')
	date_hierarchy = 'exhibition__date_start'
	ordering = ('-exhibition__date_start',)

	list_per_page = 20
	save_as = True
	save_on_top = True  # adding the Save button on top bar

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


@admin.register(Portfolio)
class PortfolioAdmin(MediaWidgetMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	form = PortfolioAdminForm

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

	list_display = ('id', 'owner', '__str__', 'exhibition', 'nominations_list', 'status')
	list_display_links = ('owner', '__str__')
	list_filter = ('nominations', 'owner', 'status')
	search_fields = (
		'title', 'owner__name', 'owner__user__first_name', 'owner__user__last_name', 'exhibition__title',
		'nominations__title'
	)
	date_hierarchy = 'exhibition__date_start'
	# autocomplete_fields = ('owner', 'exhibition')
	jazzmin_section_order = ("Основная информация", "Фото проектов", "Рейтинги", "Комментарии", "СЕО Настройки", )

	list_per_page = 50
	save_on_top = True
	save_as = True
	view_on_site = True
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

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "owner":
			kwargs["queryset"] = Exhibitors.objects.order_by('name')

		if db_field.name == "exhibition":
			kwargs["queryset"] = Exhibitions.objects.order_by('-date_start')

		return super().formfield_for_foreignkey(db_field, request, **kwargs)

	def save_model(self, request, obj, form, change):
		images = request.FILES.getlist('files')
		obj.save(images=images)  # сохраним портфолио и связанные фотографии

		delete_cached_fragment('portfolio_list', obj.owner.slug, obj.project_id, True)
		delete_cached_fragment('portfolio_list', obj.owner.slug, obj.project_id, False)
		delete_cached_fragment('portfolio_slider', obj.owner.slug, obj.project_id)
		delete_cached_fragment('participant_detail', obj.owner.id)
		# delete_cached_fragment('exhibition_header', obj.exhibition.slug)

		for nomination in obj.nominations.all():
			if nomination.category:
				delete_cached_fragment('projects_list', nomination.category.slug)
				delete_cached_fragment('sidebar', nomination.category.slug)

		victories = Winners.objects.filter(portfolio=obj)
		for victory in victories:
			delete_cached_fragment('portfolio_list', victory.exhibition.slug, victory.nomination.slug, True)
			delete_cached_fragment('portfolio_list', victory.exhibition.slug, victory.nomination.slug, False)
			delete_cached_fragment('portfolio_slider', victory.exhibition.slug, victory.nomination.slug)


@admin.register(Gallery)
class GalleryAdmin(MediaWidgetMixin, admin.ModelAdmin):
	fields = ('exhibition', 'title', 'file',)
	list_display = ('file_thumb', 'exhibition', 'title',)
	list_display_links = list_display
	search_fields = ('title', 'exhibition__title', 'exhibition__slug',)
	list_filter = ('exhibition__date_start',)
	date_hierarchy = 'exhibition__date_start'
	list_per_page = 30

	readonly_fields = ('file_thumb',)
	save_on_top = True

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)

		delete_cached_fragment('exhibition_overlay', obj.exhibition.slug)
		delete_cached_fragment('exhibition_gallery', obj.exhibition.slug)


@admin.register(Image)
class ImageAdmin(MediaWidgetMixin, admin.ModelAdmin):
	form = ImageForm
	fields = ('portfolio', 'title', 'description', 'file', 'sort')
	readonly_fields = ('file_thumb',)
	list_display = ('file_thumb', 'portfolio', 'title', 'author', 'sort',)
	list_display_links = ('file_thumb', 'portfolio', 'title',)
	list_filter = ('portfolio__owner', 'portfolio',)
	search_fields = (
		'title', 'file', 'portfolio__title', 'portfolio__owner__slug', 'portfolio__owner__name',
		'portfolio__owner__user__first_name', 'portfolio__owner__user__last_name',
	)

	list_per_page = 30

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
	prepopulated_fields = {"slug": ('name',)}  # adding name to slug field
	search_fields = ('name',)
	list_per_page = 30

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
