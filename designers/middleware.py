from .models import Designer


class SubdomainMiddleware:
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		host = request.get_host().split(':')[0]  # Убираем порт

		# 1. Определяем поддомен
		if 'X-Subdomain' in request.META:
			subdomain = request.META['X-Subdomain']
		elif host.endswith('.sd43.ru') and not host.startswith(('www.', 'sd43.ru')):
			parts = host.split('.')
			if len(parts) >= 3:
				subdomain = parts[0]
			else:
				subdomain = None
		else:
			subdomain = None

		request.subdomain = subdomain

		# 2. Находим дизайнера по поддомену (с кешированием)
		if subdomain:
			try:
				request.designer = Designer.objects.select_related('owner').get(
					slug=subdomain.lower(),
					status=2  # опубликован
				)
			except Designer.DoesNotExist:
				request.designer = None
		else:
			request.designer = None

		response = self.get_response(request)
		return response

