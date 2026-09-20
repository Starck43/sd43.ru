import logging

from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver
from django.template.loader import render_to_string

from .logic import send_email_async
from .models import Portfolio, Winners, Image
from .cache import invalidate_portfolio_cache
from .utils import set_user_group

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=Portfolio)
def portfolio_post_save(sender, instance, created, **kwargs):
	"""
	Обработчик для сохранения изображений портфолио и сброса кэша страниц.
	"""
	if hasattr(instance, '_images_to_save') and instance._images_to_save:
		# Получаем максимальный sort для этого портфолио
		max_sort = Image.objects.filter(portfolio=instance).aggregate(max_sort=models.Max('sort'))['max_sort'] or 0

		for idx, image_file in enumerate(instance._images_to_save, start=1):
			try:
				Image.objects.create(
					portfolio=instance,
					sort=max_sort + idx,
					file=image_file
				)

			except Exception as e:
				logger.error(f"Error saving image for portfolio {instance.id}: {e}")

		# Очищаем временный атрибут
		del instance._images_to_save

	invalidate_portfolio_cache(instance)


@receiver([post_save, post_delete], sender=Image)
def portfolio_image_changed(sender, instance, **kwargs):
	if instance.portfolio:
		invalidate_portfolio_cache(instance.portfolio)


@receiver(m2m_changed, sender=Portfolio.nominations.through)
def portfolio_nominations_changed(sender, instance, **kwargs):
	invalidate_portfolio_cache(instance)


@receiver([post_save, post_delete], sender=Winners)
def portfolio_victory_changed(sender, instance, **kwargs):
	invalidate_portfolio_cache(instance.portfolio)


@receiver(user_signed_up, dispatch_uid="new_user_notification")
def user_signed_up_handler(request, user, sociallogin=None, **kwargs):
	"""Обработчик регистрации нового пользователя"""

	# 1. Назначение группы
	user = set_user_group(request, user)

	# Если set_user_group меняет поля самой модели (например, user.is_staff = True)
	# user.save(update_fields=['is_staff', 'is_active'])

	logger.info(f'Регистрация пользователя{" через соцсети" if sociallogin else ""}: {user.email}.')

	# 2. Формирование URL
	host_url = settings.DOMAIN_URL

	template = render_to_string('account/admin_email_confirm.html', {
		'user': user,
		'host_url': host_url,
		'admin_url': f"{host_url}/admin/auth/user/{user.id}/change/"
	})

	# 3. Отправка
	send_email_async(
		subject='Регистрация нового пользователя на сайте sd43.ru!',
		html_content=template
	)
