from django.contrib import admin

from exhibition.admin import MetaSeoFieldsAdmin
from exhibition.mixins import ImagePreviewMixin, MediaWidgetMixin
from .forms import DesignerForm
from .models import Designer, Customer, Achievement

admin.site.site_title = 'Сайты дизайнеров'
admin.site.site_header = 'Сайты дизайнеров'


class CustomerInline(MediaWidgetMixin, admin.StackedInline):
	model = Customer
	# template = 'admin/exhibition/edit_inline/stacked.html'
	extra = 1
	show_change_link = True
	fields = ('logo', 'name', 'link', )
	# list_display = ('logo', 'name',)
	# list_editable = ['name']
	classes = ['customers-inline-tab']


class AchievementInline(MediaWidgetMixin, admin.StackedInline):
	model = Achievement
	# template = 'admin/exhibition/edit_inline/stacked.html'
	extra = 0
	show_change_link = True
	fields = ('cover', 'title', 'subtitle', 'description', 'group', 'link', 'date', )
	list_display = ('title', 'group', 'date',)
	# list_editable = ['title']
	classes = ['achievements-inline-tab']


@admin.register(Customer)
class CustomerAdmin(ImagePreviewMixin, MediaWidgetMixin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('logo',)

	fields = ('logo', 'designer', 'name', 'excerpt', 'link')
	list_display = ('designer', 'name', 'excerpt')
	list_display_links = ('designer', 'name')


@admin.register(Achievement)
class AchievementAdmin(ImagePreviewMixin, MediaWidgetMixin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('cover',)

	fields = ('cover', 'designer', 'title', 'description', 'date', 'group', 'link')
	list_display = ('designer', 'title', 'subtitle',)
	list_display_links = ('designer', 'title',)


@admin.register(Designer)
class DesignerAdmin(ImagePreviewMixin, MediaWidgetMixin, MetaSeoFieldsAdmin, admin.ModelAdmin):
	PREVIEW_FIELDS = ('logo', )

	class Media:
		js = ['/static/js/designers.min.js']

	form = DesignerForm
	list_display = ('id', 'owner', 'slug', 'status')
	list_display_links = ('id', 'owner')
	filter_horizontal = ('exh_portfolio', 'add_portfolio', 'partners')
	search_fields = ('title', 'slug')
	list_per_page = 50

	inlines = [AchievementInline, CustomerInline]

	fieldsets = (
		(
			"Общая информация", {
				"fields": (
					'owner', 'slug', 'avatar', 'logo', 'title', 'about', 'background', 'whatsapp', 'telegram',
					'show_phone', 'show_email', 'status', 'pub_date_start', 'pub_date_end', 'comment',
				),
				"classes": ('',)
			}
		),
		(
			"Портфолио", {
				'fields': ('exh_portfolio', 'add_portfolio'),
				"classes": ('',)
			},
		),
		(
			"Партнеры", {
				'fields': ('partners',),
				"classes": ('',)
			},
		),
		(
			"CEO", {
				'fields': MetaSeoFieldsAdmin.meta_fields,
				"classes": ('',)
			},
		),
	)

