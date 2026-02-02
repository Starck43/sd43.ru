from django.contrib import admin
from django.contrib.auth.models import User

from .models import Category, Article
from exhibition.models import Exhibitors

from exhibition.services import delete_cached_fragment

admin.site.site_title = 'Статьи'
admin.site.site_header = 'Статьи'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	#fields = ('name', 'slug',)
	list_display = ('name',)
	prepopulated_fields = {"slug": ('name',)}

	def save_model(self, request, obj, form, change):
		delete_cached_fragment('sidebar','articles')
		super().save_model(request, obj, form, change)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
	fields = ('category', 'owner', 'title', 'slug', 'content',)
	list_display = ('id', 'title',  'category', 'owner', 'modified_date',)
	list_display_links = ('title',)
	list_per_page = 20
	date_hierarchy = 'modified_date'
	prepopulated_fields = {"slug": ('title',)}

	def save_model(self, request, obj, form, change):
		delete_cached_fragment('sidebar','articles')
		delete_cached_fragment('articles')
		delete_cached_fragment('article', obj.id)
		super().save_model(request, obj, form, change)

	""" Отобразим список авторов статьи только для участников, партнеров, жюри"""
	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "owner":
			kwargs["queryset"] = User.objects.filter(groups__name__in=['Exhibitors', 'Partners', 'Jury']).order_by('last_name')
		return super().formfield_for_foreignkey(db_field, request, **kwargs)

	""" заменим вывод User.username в списке авторов статьи на полное имя """
	def get_name(self):
		if self.first_name or self.last_name:
			return '{} {}'.format(self.last_name.capitalize(), self.first_name.capitalize())
		else:
			return self.username

	User.add_to_class("__str__", get_name)
