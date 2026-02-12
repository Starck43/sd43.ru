from django.conf import settings
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.db.models import ImageField, FileField
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.html import format_html
from sorl.thumbnail import get_thumbnail

from ads.models import Banner
from .forms import ImageInlineForm, ImageInlineFormSet
from .models import MetaSEO, Exhibitors, Jury, Partners
from .services import delete_cached_fragment
from .widgets import MediaWidget


class ImagePreviewMixin:
	"""
	Base admin для отображения image preview.
	"""

	PREVIEW_FIELDS = ()
	THUMB_SIZE = getattr(settings, 'ADMIN_THUMBNAIL_SIZE', [80, 80])

	def _render_preview(self, obj, field_name):
		field = getattr(obj, field_name, None)

		if not field or not field.name:
			return format_html(
				'<img src="/media/site/no-image.png" style="width:{}px;height:{}px;">',
				self.THUMB_SIZE[0],
				self.THUMB_SIZE[1],
			)

		return format_html(
			'<img src="{}" style="width:{}px; height:auto; object-fit:contain;">',
			field.url,
			self.THUMB_SIZE[0]
		)

	def get_list_display(self, request):
		display = list(super().get_list_display(request))

		for field in self.PREVIEW_FIELDS:
			method_name = f'{field}_preview'

			if not hasattr(self, method_name):

				try:
					# Получаем поле из модели
					model_field = self.model._meta.get_field(field)
					field_verbose_name = model_field.verbose_name
				except (FieldDoesNotExist, AttributeError):
					# Если не нашли или нет verbose_name, используем fallback
					field_verbose_name = field.replace('_', ' ').title()

				def _fn(obj, f=field):
					return self._render_preview(obj, f)

				_fn.short_description = field_verbose_name
				setattr(self, method_name, _fn)

			display.insert(0, method_name)

		return tuple(display)


class MediaWidgetMixin:
	def formfield_for_dbfield(self, db_field, request, **kwargs):
		if isinstance(db_field, (FileField, ImageField)):
			# Создаем виджет и передаем ему поле
			widget = MediaWidget(field=db_field)
			kwargs['widget'] = widget
			return db_field.formfield(**kwargs)

		return super().formfield_for_dbfield(db_field, request, **kwargs)


class ImagesInlineAdminMixin(admin.StackedInline):
	form = ImageInlineForm
	formset = ImageInlineFormSet
	template = 'admin/exhibition/edit_inline/stacked_images.html'

	fields = ('file', 'title', 'filename')
	readonly_fields = ('filename',)

	show_change_link = True
	min_num = 0
	max_num = 20  # Максимум 20 изображений
	extra = 0

	class Media:
		css = {
			'all': (
				'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
				'admin/css/portfolio-images.min.css',
			)
		}
		js = (
			# 'admin/js/vendor/jquery/jquery.js',
			'https://cdnjs.cloudflare.com/ajax/libs/Sortable/1.14.0/Sortable.min.js',
			'admin/js/portfolio-images.min.js',
		)


class PersonAdminMixin(ImagePreviewMixin, MediaWidgetMixin):
	"""Mixin для добавления полей Person в админку"""

	PREVIEW_FIELDS = ('logo',)

	prepopulated_fields = {"slug": ('name',)}
	list_display = ('user_name', 'name',)
	list_display_links = ('user_name', 'name',)
	list_per_page = 20
	search_fields = ('name', 'slug', 'user__first_name', 'user__last_name', 'description',)

	@admin.display(description='Пользователь', empty_value='<Не определен>')
	def user_name(self, obj):
		if not obj.user:
			return None

		return obj.user_name

	def get_fieldsets(self, request, obj=None):
		fieldsets = (
			(None, {
				'classes': ('person-block',),
				'fields': ('user', ('logo',), 'name', 'slug', 'description', 'sort',)
			}),
		)
		fieldsets += super().get_fieldsets(request, obj) or ()

		return fieldsets

	def get_search_results(self, request, queryset, search_term):
		queryset, use_distinct = super().get_search_results(
			request, queryset, search_term
		)

		if 'autocomplete' in request.path:
			queryset = queryset.order_by('name')

		return queryset, use_distinct

	@staticmethod
	def clear_person_cache(obj):
		absolute_url = obj.__class__.__name__.lower()

		# 1. Базовые варианты
		delete_cached_fragment('persons', absolute_url, None)
		delete_cached_fragment('persons', absolute_url, '')
		delete_cached_fragment('persons', absolute_url, 'all')

		if isinstance(obj, Exhibitors):
			exhibitions = obj.exhibitors_for_exh.only('slug')
		elif isinstance(obj, Jury):
			exhibitions = obj.jury_for_exh.only('slug')
		elif isinstance(obj, Partners):
			exhibitions = obj.partners_for_exh.only('slug')
		else:
			exhibitions = []

		# 2. Для каждой выставки, где участвует этот объект
		for exh in exhibitions:
			delete_cached_fragment('persons', absolute_url, exh.slug)

			# Также очищаем кэш контента выставки
			delete_cached_fragment('exhibition_content', exh.slug)

		return f"Cleared cache for {absolute_url}"


class ProfileAdminMixin:
	"""Mixin для добавления полей Profile в админку"""

	def get_fieldsets(self, request, obj=None):
		fieldsets = (
			('Профиль', {
				'classes': ('profile-block',),
				'fields': ('address', 'phone', 'email', 'site', 'vk', 'tg', 'instagram'),
			}),
		)
		fieldsets += super().get_fieldsets(request, obj) or ()

		return fieldsets

	def get_list_display(self, request):
		list_display = super().get_list_display(request)
		return list_display


class ExhibitionsYearsMixin:
	"""Миксин для списков участников, жюри, партнеров"""

	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)

		# Определяем тип страницы
		self.is_all_years_page = '/all/' in request.path
		self.is_root_page = self._is_root_page(request.path)

	def _is_root_page(self, path):
		"""Определяем, корневая ли это страница"""
		absolute_url = self.model.__name__.lower()
		root_paths = [
			f'/{absolute_url}/',
			f'/{absolute_url}',
		]
		return path in root_paths

	def get_queryset(self):
		model_name = self.model.__name__.lower()
		related_name = f'{model_name}_for_exh'

		if self.is_all_years_page:
			# Для "всех годов" - добавляем аннотацию для сортировки если нужно
			if hasattr(self, 'queryset') and self.queryset is not None:
				qs = self.queryset
			else:
				qs = self.model.objects.all()

			return qs.prefetch_related(related_name).distinct()

		elif self.kwargs.get('exh_year'):
			# Для конкретного года
			if hasattr(self, 'queryset') and self.queryset is not None:
				qs = self.queryset
			else:
				qs = self.model.objects.all()

			return qs.prefetch_related(related_name).filter(
				**{f'{related_name}__slug': self.kwargs['exh_year']}
			).distinct()

		return self.model.objects.none()

	def get(self, request, *args, **kwargs):
		if self.is_root_page:
			# Ленивый импорт внутри метода
			from exhibition.models import Exhibitions

			today = timezone.now()
			current_exhibition = Exhibitions.objects.filter(
				date_end__gte=today
			).order_by('date_start').first()

			if current_exhibition:
				return redirect(
					f'exhibition:{self.model.__name__.lower()}-list-year',
					exh_year=current_exhibition.slug
				)

			return redirect(f'exhibition:{self.model.__name__.lower()}-list-all')

		return super().get(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['page_title'] = self.model._meta.verbose_name_plural
		context['absolute_url'] = self.model.__name__.lower()
		context['exh_year'] = self.kwargs.get('exh_year')
		context['is_all_years'] = self.is_all_years_page
		return context


class ProjectsLazyLoadMixin:
	PAGE_SIZE = getattr(settings, 'PORTFOLIO_COUNT_PER_PAGE', 20)

	def init_pagination(self, request):
		self.page = int(request.GET.get('page', 1))
		self.is_next_page = False

	def paginate_queryset(self, queryset):
		start = (self.page - 1) * self.PAGE_SIZE
		limit = self.PAGE_SIZE + 1

		items = list(queryset[start:start + limit])
		self.is_next_page = len(items) > self.PAGE_SIZE

		return items[:self.PAGE_SIZE]

	@staticmethod
	def enrich_queryset_with_thumbnails(queryset):
		default_quality = getattr(settings, 'THUMBNAIL_QUALITY', 85)

		for item in queryset:
			cover = item.get('project_cover')
			if not cover:
				continue

			mini = get_thumbnail(cover, '100x100', crop='center', quality=75)
			xs = get_thumbnail(cover, '320', quality=default_quality)
			sm = get_thumbnail(cover, '576', quality=default_quality)

			item.update({
				'thumb_mini': settings.MEDIA_URL + str(mini),
				'thumb_xs': settings.MEDIA_URL + str(xs),
				'thumb_sm': settings.MEDIA_URL + str(sm),
				'thumb_xs_w': 320,
				'thumb_sm_w': 576,
			})

		return queryset

	def build_projects_response(self, queryset):
		queryset = self.enrich_queryset_with_thumbnails(queryset)

		return JsonResponse({
			'current_page': self.page,
			'next_page': self.is_next_page,
			'projects_list': list(queryset),
			'default_placeholder': settings.MEDIA_URL + getattr(settings, 'DEFAULT_NO_IMAGE', ''),
		})


class BannersMixin:
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		model_name = self.model.__name__.lower()
		banners = Banner.get_banners(model_name)
		context['ads_banners'] = list(banners)
		if banners and banners[0].is_general:
			context['general_banner'] = banners[0]
			del context['ads_banners'][0]
		return context


class MetaSeoMixin:
	object = None

	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['meta'] = MetaSEO.get_content(self.model, self.object.id if self.object else None)
		return context
