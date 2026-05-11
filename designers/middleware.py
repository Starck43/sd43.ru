from django.contrib.sites.models import Site
from .models import Designer


class SubdomainMiddleware:
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		host = request.get_host().split(':')[0]  # Убираем порт

		# Получаем основной домен из Sites framework
		try:
			main_domain = Site.objects.get_current().domain
		except:
			# Fallback на случай ошибки
			main_domain = None

		# 1. Определяем поддомен
		if 'X-Subdomain' in request.META:
			subdomain = request.META['X-Subdomain']
		elif main_domain and host.endswith(main_domain) and not host.startswith(('www.', main_domain.split('.')[0])):
			# Динамическая проверка: host заканчивается на main_domain
			parts = host.split('.')
			domain_parts = main_domain.split('.')
			if len(parts) == len(domain_parts) + 1:
				# Если частей на одну больше, чем в основном домене -> это поддомен
				subdomain = parts[0]
			else:
				subdomain = None
		else:
			subdomain = None

		request.subdomain = subdomain

		# 2. Находим дизайнера по поддомену
		if subdomain:
			try:
				request.designer = Designer.objects.get_by_slug(subdomain.lower())
			except Designer.DoesNotExist:
				request.designer = None
		else:
			request.designer = None

		response = self.get_response(request)
		return response
