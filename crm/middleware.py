from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


class AjaxMiddleware:
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		request.is_ajax = (
				request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
				request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
		)

		return self.get_response(request)


class FixPermissionMiddleware(MiddlewareMixin):
	def process_request(self, request):
		if request.path.startswith('/admin/'):
			# Сохраняем оригинальные методы
			if not hasattr(self, '_original_str'):
				self._original_contenttype_str = ContentType.__str__
				self._original_permission_str = Permission.__str__

			# Исправляем ContentType.__str__
			def safe_contenttype_str(self):
				return f"{self.app_label} | {self.model}"

			# Исправляем Permission.__str__
			def safe_permission_str(self):
				try:
					ct_str = f"{self.content_type.app_label} | {self.content_type.model}"
				except:
					ct_str = f"ContentType #{self.content_type_id}"
				return f"{ct_str} | {self.name}"

			ContentType.__str__ = safe_contenttype_str
			Permission.__str__ = safe_permission_str

	def process_response(self, request, response):
		# Восстанавливаем оригинальные методы
		if hasattr(self, '_original_str'):
			ContentType.__str__ = self._original_contenttype_str
			Permission.__str__ = self._original_permission_str
		return response
