import re
import unicodedata

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
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
