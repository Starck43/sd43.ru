from django.contrib.auth.models import Group

from typing import TYPE_CHECKING

from exhibition.models import Jury, Exhibitors

if TYPE_CHECKING:
	from exhibition.models import Portfolio
	from rating.models import Rating


def is_exhibitor_of_exhibition(user, exhibition):
	"""Проверка, является ли пользователь участником выставки"""
	if not user or not user.is_authenticated:
		return False

	return exhibition.exhibitors.filter(user=user, user__is_active=True).exists()


def is_jury_member(user):
	"""Проверка, является ли пользователь членом жюри"""
	if not user or not user.is_authenticated:
		return False

	try:
		return Jury.objects.filter(user=user, user__is_active=True).exists()
	except:
		return False


def get_exhibitor_for_user(user):
	"""Возвращает объект Exhibitors для пользователя или None"""
	if not user or not user.is_authenticated:
		return None
	try:
		return Exhibitors.objects.get(user=user, user__is_active=True)
	except Exhibitors.DoesNotExist:
		return None


def can_rate_portfolio(user, portfolio: 'Portfolio', is_jury=None):
	"""Проверяет, может ли пользователь оценивать работу в зависимости от фазы выставки."""

	exhibition = portfolio.exhibition

	if not exhibition:
		return True, "", 0

	if (not user or not user.is_authenticated) and exhibition.is_users_voting_active:
		return False, "Войдите в систему, чтобы участвовать в голосовании", 0

	if user:
		user_rating: 'Rating' = portfolio.ratings.filter(user=user).first()

		# Фаза голосования жюри
		if is_jury and exhibition.is_jury_voting_active:
			return True, "Голосование открыто", user_rating.star if user_rating and user_rating.star > 0 else 0

		# После окончания выставки — голосование открыто
		if not is_jury and exhibition.is_users_voting_active:
			if user_rating and user_rating.star > 0:
				return False, "Вы уже проголосовали", user_rating.star
			return True, "Голосование открыто", 0

	return False, "Голосование закрыто", 0


def set_user_group(request, user):
	""" Set User group on SignupForm via account/social account"""

	is_exhibitor = request.POST.get('exhibitor', False)
	if is_exhibitor == 'on':
		group_name = "Exhibitors"
	else:
		group_name = "Members"

	try:
		group = Group.objects.get(name=group_name)
		user.groups.add(group)

	except Group.DoesNotExist:
		pass

	return user
