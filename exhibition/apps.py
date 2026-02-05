from django.apps import AppConfig
from watson import search as watson


class ExhibitionConfig(AppConfig):
	name = 'exhibition'
	verbose_name = 'Сфера дизайна'
	default_auto_field = 'django.db.models.BigAutoField'

	def ready(self):
		import exhibition.signals

		Exhibtitors = self.get_model("Exhibitors")
		watson.register(Exhibtitors, store=("description",))
		Jury = self.get_model("Jury")
		watson.register(Jury, store=("excerpt", "description",))
		Partners = self.get_model("Partners")
		watson.register(Partners, store=("description",))
		Events = self.get_model("Events")
		watson.register(Events)
		Exhibtions = self.get_model("Exhibitions")
		watson.register(Exhibtions, ExhibitionsAdapter)
		Portfolio = self.get_model("Portfolio")
		watson.register(Portfolio.objects.prefetch_related('images'), PortfolioAdapter)
		Nominations = self.get_model("Nominations")
		watson.register(Nominations, NominationsAdapter, fields=("category__title", "category__description", "category__logo"))


class ExhibitionsAdapter(watson.SearchAdapter):
	def get_title(self, obj):
		return 'Выставка "%s"' % obj.title

	def get_description(self, obj):
		return '<b>Дата проведения:</b> %s - %s %s' % (obj.date_start.strftime('%d.%m.%Y'), obj.date_end.strftime('%d.%m.%Y'),obj.description)


class NominationsAdapter(watson.SearchAdapter):
	def get_description(self, obj):
		if obj.category:
			return '<p>%s</p><b>Категория:</b> %s' % (obj.description, obj.category.title)
		else:
			return '<p>%s</p>' % (obj.description)


class PortfolioAdapter(watson.SearchAdapter):
	def get_description(self, obj):
		return '<p><b>Автор проекта:</b> %s</p>%s' % (obj.owner.name, obj.description)
