from django.contrib.sitemaps import Sitemap

from .models import Designer


class DesignerMainSitemap(Sitemap):
	"""Sitemap для главной страницы дизайнера"""
	priority = 1.0
	changefreq = 'weekly'

	def items(self):
		return Designer.objects.published()

	def location(self, item):
		# Для поддомена - корень
		return '/'


class DesignerPortfolioSitemap(Sitemap):
	"""Sitemap для страницы портфолио дизайнера"""
	priority = 0.9
	changefreq = 'weekly'

	def items(self):
		# Только дизайнеры с портфолио
		return Designer.objects.with_portfolio()  # Используем менеджер

	def location(self, item):
		return '/portfolio/'


class DesignerProjectSitemap(Sitemap):
	"""Sitemap для проектов портфолио дизайнера"""
	priority = 0.8
	changefreq = 'weekly'

	def items(self):
		designers = Designer.objects.with_portfolio()
		projects = []
		for designer in designers:
			# Только активные проекты
			for portfolio in designer.exh_portfolio.filter(status=True):
				projects.append({
					'designer': designer,
					'project_id': portfolio.project_id,
					'url': f'/portfolio/{portfolio.project_id}/'
				})
			for portfolio in designer.add_portfolio.filter(status=True):
				projects.append({
					'designer': designer,
					'project_id': portfolio.project_id,
					'url': f'/portfolio/{portfolio.project_id}/'
				})
		return projects

	def location(self, item):
		return item['url']


# Sitemap для поддомена
designer_sitemaps = {
	'main': DesignerMainSitemap,
	'portfolio': DesignerPortfolioSitemap,
	'projects': DesignerProjectSitemap,
}
