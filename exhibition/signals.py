from django.db import models
from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver

from .models import Portfolio, Winners, Image
from .cache import invalidate_portfolio_cache


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
				import logging
				logger = logging.getLogger(__name__)
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
