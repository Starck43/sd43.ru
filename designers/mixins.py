from django.shortcuts import get_object_or_404, redirect
from django.http import Http404

from designers.models import Designer


class SubdomainMixin:
	"""Mixin для работы с поддоменами"""

	def get_object(self, **kwargs):
		# Если есть request.designer (из middleware), используем его
		if hasattr(self.request, 'designer') and self.request.designer:
			return self.request.designer

		slug = self.kwargs.get('slug')
		if not slug:
			raise Http404('Дизайнер не найден')

		designer = get_object_or_404(
			Designer,
			slug=slug.lower(),
			status=2
		)

		# Проверяем доступ
		if designer.status != 2:
			return redirect(designer.owner)

		return designer

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		# Добавляем subdomain в контекст шаблона
		context['subdomain'] = getattr(self.request, 'subdomain', None)
		return context
