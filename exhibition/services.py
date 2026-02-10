import re
import unicodedata
from decimal import Decimal

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Subquery, OuterRef, Avg, When, Q, CharField, Case


class ProjectsQueryService:

	@staticmethod
	def get_cover_with_rating(queryset):
		from exhibition.models import Image
		cover_subquery = Subquery(
			Image.objects.filter(portfolio=OuterRef('pk')).values('file')[:1]
		)

		return queryset.annotate(
			average=Avg('ratings__star'),
			project_cover=Case(
				When(Q(cover__isnull=True) | Q(cover=''), then=cover_subquery),
				default='cover',
				output_field=CharField()
			)
		)


class WinnersService:

	@staticmethod
	def build_winners_preview(exhibition):
		from collections import defaultdict

		result = {
			'exhibition_id': exhibition.id,
			'items': [],
			'conflicts': [],
		}

		# Группируем портфолио по номинациям
		nomination_portfolios = defaultdict(list)

		# Загружаем все портфолио с оценками
		portfolios_qs = (
			exhibition.portfolio_set
			.filter(status=True)
			.prefetch_related('nominations')
			.select_related('owner')
		)

		# Собираем портфолио по номинациям
		for portfolio in portfolios_qs:
			portfolio_stats = portfolio.get_rating_stats()
			for nomination in portfolio.nominations.all():
				nomination_portfolios[nomination.id].append({
					'portfolio': portfolio,
					'stats': portfolio_stats,
				})

		# Обрабатываем каждую номинацию
		for nomination in exhibition.nominations.all():
			portfolios_in_nomination = nomination_portfolios.get(nomination.id, [])

			# Если в номинации нет портфолио
			if not portfolios_in_nomination:
				result['items'].append({
					'nomination_id': nomination.id,
					'winners': [],
					'no_participants': True,
				})
				continue

			# Проверяем, все ли портфолио оценены
			all_rated = all(p['stats']['jury_count'] > 0 for p in portfolios_in_nomination)

			if not all_rated:
				result['items'].append({
					'nomination_id': nomination.id,
					'winners': [],
					'incomplete': True,
				})
				continue

			# Формируем список оцененных портфолио
			scored = []
			for item in portfolios_in_nomination:
				if item['stats']['jury_average'] > 0:
					scored.append({
						'portfolio_id': item['portfolio'].id,
						'exhibitor_id': item['portfolio'].owner.id,
						'avg': item['stats']['jury_average'],
						'votes': item['stats']['jury_count'],
					})

			# Если нет подходящих победителей (все avg <= 0)
			if not scored:
				result['items'].append({
					'nomination_id': nomination.id,
					'winners': [],
					'no_qualified_votes': True,
				})
				continue

			# Находим победителей
			max_avg = max(scored, key=lambda x: x['avg'])['avg']
			winners = [s for s in scored if s['avg'] == max_avg]

			entry = {
				'nomination_id': nomination.id,
				'winners': winners,
			}

			result['items'].append(entry)

			if len(winners) > 1:
				result['conflicts'].append(entry)

		return result

	@staticmethod
	def serialize_preview(preview: dict) -> dict:
		"""Делает preview безопасным для хранения в session"""

		def normalize(value):
			if isinstance(value, Decimal):
				return float(value)
			return value

		return {
			'exhibition_id': preview['exhibition_id'],
			'items': [
				{
					'nomination_id': item['nomination_id'],
					'winners': [
						{
							'portfolio_id': w['portfolio_id'],
							'exhibitor_id': w['exhibitor_id'],
							'avg': normalize(w['avg']),
							'votes': w['votes'],
						}
						for w in item['winners']
					],
					'no_votes': item.get('no_votes', False),
				}
				for item in preview['items']
			],
			'conflicts': [
				{
					'nomination_id': c['nomination_id'],
					'winners': [
						{
							'portfolio_id': w['portfolio_id'],
							'exhibitor_id': w['exhibitor_id'],
							'avg': normalize(w['avg']),
							'votes': w['votes'],
						}
						for w in c['winners']
					],
				}
				for c in preview['conflicts']
			],
		}

	@staticmethod
	def deserialize_preview(session_data: dict) -> dict:
		"""Восстанавливает объекты из сессии"""
		from .models import Exhibitions, Nominations, Portfolio

		# Получаем объекты за один запрос с оптимизацией
		exhibition = Exhibitions.objects.select_related().get(
			id=session_data['exhibition_id']
		)

		# Собираем все ID для пакетной загрузки
		nomination_ids = set()
		portfolio_ids = set()

		for item in session_data['items']:
			nomination_ids.add(item['nomination_id'])
			for w in item['winners']:
				portfolio_ids.add(w['portfolio_id'])

		# Загружаем все номинации за один запрос
		nominations_dict = {
			n.id: n for n in Nominations.objects.filter(id__in=nomination_ids)
		}

		# Загружаем все портфолио с владельцами за один запрос
		portfolios = Portfolio.objects.filter(
			id__in=portfolio_ids
		).select_related('owner')
		portfolios_dict = {p.id: p for p in portfolios}

		items = []
		conflicts = []

		# Восстанавливаем items
		for item_data in session_data['items']:
			nomination = nominations_dict.get(item_data['nomination_id'])
			if not nomination:
				continue

			winners = []
			for w_data in item_data['winners']:
				portfolio = portfolios_dict.get(w_data['portfolio_id'])
				if portfolio:
					winners.append({
						'portfolio': portfolio,
						'avg': Decimal(str(w_data['avg'])),
						'votes': w_data['votes'],
					})

			item = {
				'nomination': nomination,
				'winners': winners,
				'no_votes': item_data.get('no_votes', False),
			}
			items.append(item)

		# Восстанавливаем conflicts
		for conflict_data in session_data['conflicts']:
			nomination = nominations_dict.get(conflict_data['nomination_id'])
			if not nomination:
				continue

			winners = []
			for w_data in conflict_data['winners']:
				portfolio = portfolios_dict.get(w_data['portfolio_id'])
				if portfolio:
					winners.append({
						'portfolio': portfolio,
						'avg': Decimal(str(w_data['avg'])),
						'votes': w_data['votes'],
					})

			conflicts.append({
				'nomination': nomination,
				'winners': winners,
			})

		return {
			'exhibition': exhibition,
			'items': items,
			'conflicts': conflicts,
		}

	@staticmethod
	@transaction.atomic
	def save_winners(preview, manual_selection=None):
		exhibition = preview['exhibition']

		exhibition.exhibition_for_winner.all().delete()

		for item in preview['items']:
			# Пропускаем номинации без победителей
			if not item.get('winners'):
				continue

			nomination = item['nomination']
			winners = item['winners']

			if manual_selection:
				selected_id = manual_selection.get(str(nomination.id))
				if selected_id:
					winners = [
						w for w in winners
						if str(w['portfolio'].id) == selected_id
					]
					# Если после фильтрации winners пуст, пропускаем
					if not winners:
						continue

			for w in winners:
				portfolio = w['portfolio']

				# Дополнительная проверка на avg > 0
				if w['avg'] <= 0:
					continue

				exhibition.exhibition_for_winner.create(
					nomination=nomination,
					exhibitor=portfolio.owner,
					portfolio=portfolio
				)


def delete_cached_fragment(fragment_name, *args):
	""" Reset cache """
	key = make_template_fragment_key(fragment_name, args or None)
	cache.delete(key)
	return key


def unicode_emoji(data, direction='encode'):
	""" Encoding/decoding emoji in string data """
	if data:
		if direction == 'encode':
			emoji_pattern = re.compile(
				u"["
				u"\u2600-\u26FF"  # Unicode Block 'Miscellaneous Symbols'
				u"\U0001F600-\U0001F64F"  # emoticons
				u"\U0001F300-\U0001F5FF"  # symbols & pictographs
				u"\U0001F680-\U0001F6FF"  # transport & map symbols
				u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
				"]",
				flags=re.UNICODE
			)

			return re.sub(emoji_pattern, lambda y: ':' + unicodedata.name(y.group(0)) + ':', data)
		elif direction == 'decode':
			return re.sub(r':([^a-z]+?):', lambda y: unicodedata.lookup(y.group(1)), data)
		else:
			return data
	else:
		return ''


def is_mobile(request):
	""" Return True if the request comes from a mobile device """
	import re

	agent = re.compile(r".*(iphone|mobile|androidtouch)", re.IGNORECASE)

	if agent.match(request.META['HTTP_USER_AGENT']):
		return True
	else:
		return False


def update_google_sitemap():
	...
