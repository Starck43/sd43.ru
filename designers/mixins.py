from django.shortcuts import redirect
from django.http import Http404


class DesignerAccessMixin:
	"""Mixin для проверки доступа к дизайнеру"""

	def dispatch(self, request, *args, **kwargs):
		# Пробуем взять slug из разных источников
		slug = kwargs.get('slug')

		if not slug and hasattr(request, 'subdomain'):
			slug = request.subdomain

		if not slug and request.GET.get('subdomain'):  # Для разработки
			slug = request.GET.get('subdomain')

		if not slug:
			raise Http404('Дизайнер не найден')

		try:
			designer = self.model.objects.get(slug=slug)
			if designer.status != 2:
				return redirect(designer.owner)

			self.object = designer

		except self.model.DoesNotExist:
			raise Http404('Страница с таким адресом не существует!')

		return super().dispatch(request, *args, **kwargs)
