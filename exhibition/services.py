import re
import unicodedata

from django.conf import settings
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from sorl.thumbnail import get_thumbnail
from django.db.models import Subquery, OuterRef, Case, When, Q, Value, CharField


DEFAULT_COVER = getattr(
	settings,
	'DEFAULT_NO_IMAGE',
	'site/no-image.png'
)


class PortfolioImageService:
	"""Сервис для работы с изображениями портфолио"""

	DEFAULT_SIZES = {
		'mini': {'size': '100x100', 'quality': 75, 'crop': 'center'},
		'xs': {'size': '320', 'quality': 85, 'crop': None},
		'sm': {'size': '576', 'quality': 85, 'crop': None},
		'md': {'size': '768', 'quality': 85, 'crop': None},
		'lg': {'size': '1024', 'quality': 85, 'crop': None},
	}

	@classmethod
	def annotate_queryset_with_cover(cls, queryset):
		"""Аннотирует queryset полем project_cover с обложкой"""

		from exhibition.models import Image
		# Получаем первое изображение портфолио
		first_image_subquery = Image.objects.filter(
			portfolio=OuterRef('pk')
		).order_by('id').values('file')[:1]

		return queryset.annotate(
			# Сначала аннотируем файл первого изображения
			first_image_file=Subquery(first_image_subquery),
			# Затем используем Case для выбора обложки
			project_cover=Case(
				When(
					Q(cover__isnull=False) & ~Q(cover=''),
					then='cover'
				),
				When(
					# Используем проверку на существование файла
					Q(first_image_file__isnull=False),
					then='first_image_file'
				),
				default=Value(settings.DEFAULT_COVER if hasattr(settings, 'DEFAULT_COVER') else ''),
				output_field=CharField(),
			)
		)

	@classmethod
	def get_thumbnails(cls, cover_field, sizes=None):
		"""Генерирует миниатюры для изображения"""
		if not cover_field:
			return {}

		if sizes is None:
			sizes = cls.DEFAULT_SIZES

		thumbnails = {}
		for key, config in sizes.items():
			try:
				thumb = get_thumbnail(
					cover_field,
					config['size'],
					crop=config.get('crop'),
					quality=config.get('quality', 85)
				)
				thumbnails[f'thumb_{key}'] = thumb.url
				thumbnails[f'thumb_{key}_w'] = thumb.width
				thumbnails[f'thumb_{key}_h'] = thumb.height
			except Exception as e:
				# Обработка ошибок генерации миниатюр
				thumbnails[f'thumb_{key}'] = str(cover_field) if cover_field else ''
				thumbnails[f'thumb_{key}_w'] = 0
				thumbnails[f'thumb_{key}_h'] = 0

		return thumbnails

	@classmethod
	def enrich_portfolio_data(cls, portfolio_data, sizes=None):
		"""Обогащает данные портфолио миниатюрами"""
		if isinstance(portfolio_data, dict):
			if 'project_cover' in portfolio_data and portfolio_data['project_cover']:
				thumbnails = cls.get_thumbnails(portfolio_data['project_cover'], sizes)
				portfolio_data.update(thumbnails)
		elif hasattr(portfolio_data, 'project_cover') and portfolio_data.project_cover:
			# Если это объект модели
			thumbnails = cls.get_thumbnails(portfolio_data.project_cover, sizes)
			for key, value in thumbnails.items():
				setattr(portfolio_data, key, value)

		return portfolio_data

	@classmethod
	def enrich_queryset(cls, queryset, sizes=None):
		"""Обогащает queryset портфолио миниатюрами"""
		enriched = []
		for item in queryset:
			enriched_item = cls.enrich_portfolio_data(item, sizes)
			enriched.append(enriched_item)
		return enriched


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
