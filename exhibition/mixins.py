from django.contrib import admin

from .models import MetaSEO
from ads.models import Banner


class PersonAdminMixin:
	"""Mixin для добавления полей Person в админку"""

	prepopulated_fields = {"slug": ('name',)}
	list_display = ('logo_thumb', 'user_name', 'name',)
	list_display_links = ('logo_thumb', 'user_name', 'name',)
	list_per_page = 20
	search_fields = ('name', 'slug', 'user__first_name', 'user__last_name', 'description',)

	@admin.display(description='Пользователь', empty_value='<Не определен>')
	def user_name(self, obj):
		if not obj.user:
			return None

		if (not obj.user.first_name) and (not obj.user.last_name):
			return obj.user.username
		else:
			return "%s %s" % (obj.user.first_name, obj.user.last_name)

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
		return list_display + ('phone', 'email',)


class ExhibitionYearListMixin:
	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['page_title'] = self.model._meta.verbose_name_plural
		context['absolute_url'] = self.model.__name__.lower()
		context['exh_year'] = self.kwargs.get('exh_year', None)
		if not context.get('cache_timeout'):
			context['cache_timeout'] = 86400
		return context


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
