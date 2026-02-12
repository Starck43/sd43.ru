import logging

from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
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


@receiver(post_save, sender=User)
def sync_user_email_to_allauth(sender, instance, created, **kwargs):
	"""
	Синхронизация User.email → allauth EmailAddress
	Только для пользователей, созданных НЕ через allauth (админка, импорт и т.д.)
	"""

	from allauth.account.models import EmailAddress

	# Если есть связанный SocialAccount - это соцсеть
	if hasattr(instance, 'socialaccount_set') and instance.socialaccount_set.exists():
		# Это вход через соцсети - allauth сам создаст EmailAddress
		return

	# Если пользователь создан через форму регистрации allauth,
	# у него уже будет EmailAddress после вызова сигнала user_signed_up
	if not instance.email:
		EmailAddress.objects.filter(user=instance).delete()
		return

	email = instance.email.strip().lower()

	# Проверяем, существует ли уже EmailAddress для этого пользователя
	existing = EmailAddress.objects.filter(user=instance).first()

	if not existing:
		# Создаем только если его нет (для админки)
		EmailAddress.objects.get_or_create(
			user=instance,
			email=email,
			defaults={
				"verified": True,
				"primary": True,
			}
		)
	else:
		# Обновляем существующий
		updated = False

		if existing.email != email:
			existing.email = email
			updated = True

		if not existing.verified:
			existing.verified = True
			updated = True

		if not existing.primary:
			# Сначала сбрасываем primary у всех
			EmailAddress.objects.filter(user=instance).update(primary=False)
			existing.primary = True
			updated = True

		if updated:
			existing.save()


@receiver(user_signed_up, dispatch_uid="new_user_notification")
def user_signed_up_(request, user, sociallogin=None, **kwargs):
	"""Обработчик регистрации нового пользователя"""

	user = set_user_group(request, user)
	user.save()

	logger.info(f'Регистрация пользователя{" через соцсети" if sociallogin else ""}: {user.email}.')

	# Отправляем письмо администратору
	protocol = 'https' if request.is_secure() else 'http'
	host_url = f"{protocol}://{request.get_host()}"

	template = render_to_string('account/admin_email_confirm.html', {
		'user': user,
		'host_url': host_url,
		'admin_url': f"{host_url}/admin/auth/user/{user.id}/change/"
	})

	send_email_async('Регистрация нового пользователя на сайте sd43.ru!', template)
