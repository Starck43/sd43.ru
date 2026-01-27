from django.utils.timezone import now
from datetime import timedelta

from exhibition.utils import is_jury_member


def can_rate_during_exhibition(user, portfolio):
	"""Проверяет, может ли пользователь оценивать во время выставки"""
	if not portfolio.exhibition:
		return True, "Работа не участвует в выставке"

	rating_deadline = portfolio.exhibition.date_end - timedelta(days=1)

	# Если срок оценки истек
	if now().date() > rating_deadline:
		return False, "Срок выставления оценок завершен"

	# Если выставка активна - оценивать могут только жюри
	if now().date() <= rating_deadline and not is_jury_member(user):
		return False, "Во время выставки оценивать могут только члены жюри"

	return True, "Можно оценивать"
