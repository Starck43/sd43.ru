from .models import Exhibitors


def is_exhibitors_member(user):
	"""Проверка, является ли пользователь участником выставки"""
	if not user or not user.is_authenticated:
		return False
	try:
		# Админы не являются участниками выставки
		return Exhibitors.objects.filter(user=user).exists()
	except:
		return False

