from django.contrib import admin

from django.contrib.contenttypes.models import ContentType

from exhibition.mixins import ImagePreviewMixin, MediaWidgetMixin
from .models import Banner
from .forms import BannerForm

from exhibition.services import delete_cached_fragment

admin.site.site_title = 'Реклама на сайте'
admin.site.site_header = 'Рекламные баннеры'


@admin.register(Banner)
class BannerAdmin(ImagePreviewMixin, MediaWidgetMixin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('file',)

	form = BannerForm

	list_display = ('title', 'user', 'show_start', 'show_end', 'sort',)
	list_display_links = ('title',)
	list_per_page = 20

	# class Media:
	# 	js = ['/static/js/ads.min.js']

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		# сбросить кэш у страницы "статьи"
		if obj.article:
			delete_cached_fragment('article', obj.article.id)
		if obj.article or obj.is_general:
			delete_cached_fragment('articles')

	def formfield_for_manytomany(self, db_field, request, **kwargs):
		""" Отобразим список авторов статьи только для участников, партнеров, жюри"""
		if db_field.name == "pages":
			kwargs["queryset"] = ContentType.objects.filter(
				model__in=[
					'article', 'portfolio', 'exhibitions', 'categories', 'winners', 'exhibitors', 'partners',
					'jury', 'events'
				]
			)
		return super().formfield_for_manytomany(db_field, request, **kwargs)

	def get_name(self):
		# заменим название модели в ContentType
		return self.model_class()._meta.verbose_name

	ContentType.add_to_class("__str__", get_name)
