from exhibition.models import Jury, Exhibitors


def is_exhibitor_of_exhibition(user, exhibition):
	"""Проверка, является ли пользователь участником выставки"""
	if not user or not user.is_authenticated:
		return False

	return exhibition.exhibitors.filter(user=user).exists()


def is_jury_member(user):
	"""Проверка, является ли пользователь членом жюри"""
	if not user or not user.is_authenticated:
		return False

	try:
		return Jury.objects.filter(user=user).exists()

	except:
		return False


def get_exhibitor_for_user(user):
	"""Возвращает объект Exhibitors для пользователя или None"""
	if not user or not user.is_authenticated:
		return None
	try:
		return Exhibitors.objects.get(user=user)
	except Exhibitors.DoesNotExist:
		return None
