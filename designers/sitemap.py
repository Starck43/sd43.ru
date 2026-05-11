from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.shortcuts import get_object_or_404

from .models import Designer


class DesignerMainSitemap(Sitemap):
	"""Sitemap для главной страницы конкретного дизайнера"""
	priority = 1.0
	changefreq = 'weekly'

	def __init__(self, designer):
		self.designer = designer

	def items(self):
		# Возвращаем только одного дизайнера
		return [self.designer]

	def location(self, item):
		return '/'


class DesignerPortfolioSitemap(Sitemap):
	"""Sitemap для страницы портфолио конкретного дизайнера"""
	priority = 0.9
	changefreq = 'weekly'

	def __init__(self, designer):
		self.designer = designer

	def items(self):
		# Возвращаем дизайнера только если у него есть портфолио
		if self.designer.exh_portfolio.filter(status=True).exists() or \
				self.designer.add_portfolio.filter(status=True).exists():
			return [self.designer]
		return []

	def location(self, item):
		return '/portfolio/'


class DesignerProjectSitemap(Sitemap):
	"""Sitemap для проектов портфолио конкретного дизайнера"""
	priority = 0.8
	changefreq = 'weekly'

	def __init__(self, designer):
		self.designer = designer

	def items(self):
		projects = []
		# Только проекты этого дизайнера
		for portfolio in self.designer.exh_portfolio.filter(status=True):
			projects.append({
				'project_id': portfolio.project_id,
				'url': f'/portfolio/{portfolio.project_id}/'
			})
		for portfolio in self.designer.add_portfolio.filter(status=True):
			projects.append({
				'project_id': portfolio.project_id,
				'url': f'/portfolio/{portfolio.project_id}/'
			})
		return projects

	def location(self, item):
		return item['url']


# View для отображения sitemap дизайнера
def designer_sitemap_view(request, slug):
	"""Генерирует sitemap.xml для конкретного дизайнера"""

	# Получаем дизайнера
	designer = get_object_or_404(Designer.objects.published(), slug=slug)

	# Создаем sitemap классы с привязкой к дизайнеру
	sitemaps = {
		'main': DesignerMainSitemap(designer),
		'portfolio': DesignerPortfolioSitemap(designer),
		'projects': DesignerProjectSitemap(designer),
	}

	# Возвращаем sitemap
	return sitemap(request, sitemaps=sitemaps)
