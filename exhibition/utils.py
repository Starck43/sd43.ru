from .models import Exhibitors


def is_exhibitor_of_exhibition(user, exhibition):
	"""Проверка, является ли пользователь участником выставки"""
	if not user or not user.is_authenticated:
		return False
	try:
		# Админы не являются участниками выставки
		return Exhibitors.objects.filter(
			user=user, 
			exhibition=exhibition
		).exists()
	except:
		return False

