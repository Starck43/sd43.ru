from django.contrib import admin

from exhibition.services import delete_cached_fragment
from .models import Rating, Reviews

admin.site.site_title = 'Рейтинг портфолио'
admin.site.site_header = 'Рейтинг'


class RatingInline(admin.TabularInline):
	model = Rating
	fields = ('star', 'user', 'is_jury_rating', 'updated_at')
	readonly_fields = ('star', 'user', 'updated_at')
	verbose_name_plural = "Оценки проекта"

	show_change_link = False
	extra = 0


class ReviewInline(admin.StackedInline):
	model = Reviews
	fields = ('fullname', 'portfolio', 'message', 'posted_date')
	readonly_fields = ('user', 'group', 'parent', 'fullname', 'portfolio', 'message', 'posted_date')

	show_change_link = False
	extra = 0


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
	list_display = ('star', 'portfolio', 'get_exhibition', 'get_fullname', 'created_at', 'is_jury_rating')
	list_filter = ('star', 'is_jury_rating', 'portfolio__exhibition')
	search_fields = ('user__username', 'user__first_name', 'user__last_name')
	date_hierarchy = 'portfolio__exhibition__date_start'
	readonly_fields = ('ip',)

	@admin.display(
		description='Выставка',
		empty_value='<Вневыставочный проект>',
		ordering='-portfolio__exhibition__date_start'
	)
	def get_exhibition(self, obj):
		if obj.portfolio and obj.portfolio.exhibition:
			return obj.portfolio.exhibition.exh_year

	@admin.display(description='Автор рейтинга', ordering='user__last_name')
	def get_fullname(self, obj):
		return obj.fullname

	def save_model(self, request, obj, form, change):
		super().save_model(request, obj, form, change)
		delete_cached_fragment('portfolio', obj.portfolio.id)


@admin.register(Reviews)
class ReviewAdmin(admin.ModelAdmin):
	list_display = ('id', 'group', 'portfolio', 'fullname', 'parent', 'message', 'posted_date',)

	# def save_model(self, request, obj, form, change):
	# 	super().save_model(request, obj, form, change)

	# 	delete_cached_fragment('portfolio_review', obj.portfolio.id)
