import re
import unicodedata
import hashlib
import threading
import locale

from os import path
from django.conf import settings

from django import template
from django.db.models import Model
from django.utils.safestring import mark_safe, SafeString

register = template.Library()


@register.simple_tag
def site_version():
	return getattr(settings, 'VERSION', '1.0.0')


@register.filter
def verbose_name(obj):
	return obj._meta.verbose_name


@register.filter
def verbose_name_plural(obj):
	return obj._meta.verbose_name_plural


@register.filter
def file_exists(obj):
	return True if path.exists(obj.path) else False


@register.filter
def filename(obj):
	return obj.rsplit('/', 1)[-1]


@register.filter
def basename(value):
	"""Возвращает только имя файла из пути"""
	if not value:
		return ''
	return path.basename(str(value))


@register.filter
def to_string(obj):
	return " ".join(obj)


@register.filter
def admin_change_url(obj, app='exhibition'):
	if isinstance(obj, str | SafeString):
		model_name = str(obj)
	elif isinstance(obj, Model):
		model_name = obj._meta.model_name
	else:
		raise ValueError(
			f'admin_change_url: unsupported type {type(obj)}'
		)

	return f'admin:{app}_{model_name}_change'


@register.filter
def decode_emoji(obj):
	return re.sub(r':([^a-z]+?):', lambda y: unicodedata.lookup(y.group(1)), obj)


# return unique query list
@register.filter
def distinct(items, attr_name):
	return set([getattr(i, attr_name) for i in items])


@register.filter
def count_range(value, start_index=0):
	return range(start_index, value + start_index)


@register.filter
def get_item(dictionary, key):
	if not isinstance(dictionary, dict):
		return []
	return dictionary.get(key, [])


class UrlCache(object):
	_md5_sum = {}
	_lock = threading.Lock()

	@classmethod
	def get_md5(cls, file):
		try:
			return cls._md5_sum[file]
		except KeyError:
			with cls._lock:
				try:
					if hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
						filepath = settings.STATICFILES_DIRS[0]
					else:
						filepath = settings.STATIC_ROOT

					md5 = cls.calc_md5(path.join(filepath, file))[:8]
					value = '%s%s?v=%s' % (settings.STATIC_URL, file, md5)
				except IsADirectoryError:
					value = settings.STATIC_URL + file
				cls._md5_sum[file] = value
				return value

	@classmethod
	def calc_md5(cls, file_path):
		with open(file_path, 'rb') as fh:
			m = hashlib.md5()
			while True:
				data = fh.read(8192)
				if not data:
					break
				m.update(data)
			return m.hexdigest()


@register.simple_tag
def md5url(model_object):
	return UrlCache.get_md5(model_object)


@register.filter('input_type')
def input_type(ob):
	"""
	Extract form field type
	:param ob: form field
	:return: string of form field widget type
	"""
	return ob.field.widget.__class__.__name__


@register.filter(name='add_classes')
def add_classes(value, arg):
	"""
	Add provided classes to form field
	:param value:
	:param arg: string of classes seperated by ' '
	:return: edited field
	"""
	css_classes = value.field.widget.attrs.get('class', '')
	# check if class is set or empty and split its content to list (or init list)
	if css_classes:
		css_classes = css_classes.split(' ')
	else:
		css_classes = []
	# prepare new classes to list
	args = arg.split(' ')
	for a in args:
		if a not in css_classes:
			css_classes.append(a)
	# join back to single string
	return value.as_widget(attrs={'class': ' '.join(css_classes)})


@register.filter
def is_svg(file):
	"""Проверяет, является ли файл SVG"""
	if not file:
		return False
	return file.name.lower().endswith('.svg')


@register.filter
def get_image_html(file, size="100px"):
	"""Улучшенная версия для работы с SVG"""
	if not file:
		return ""

	if file.name.lower().endswith('.svg'):
		return mark_safe(
			f'<img src="{file.url}" style="max-width: {size}; max-height: {size};" />'
		)
	else:
		# Для обычных изображений
		from django.utils.html import escape
		return mark_safe(
			f'<img src="{file.url}" style="max-width: {size}; max-height: {size};" />'
		)


@register.filter
def date_with_declension(value):
	"""Дата с правильным падежом для 'до'"""
	if not value:
		return ""

	try:
		# Устанавливаем русскую локаль
		locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
	except locale.Error:
		try:
			locale.setlocale(locale.LC_TIME, 'ru_RU')
		except locale.Error:
			# Если не удалось установить русскую локаль
			return f"{value.day}.{value.month}.{value.year}"

	# Форматируем дату (месяц будет на русском)
	date_str = value.strftime("%d %B %Y")

	replacements = {
		'январь': 'января',
		'февраль': 'февраля',
		'март': 'марта',
		'апрель': 'апреля',
		'май': 'мая',
		'июнь': 'июня',
		'июль': 'июля',
		'август': 'августа',
		'сентябрь': 'сентября',
		'октябрь': 'октября',
		'ноябрь': 'ноября',
		'декабрь': 'декабря',
	}

	for nom, gen in replacements.items():
		if nom in date_str:
			date_str = date_str.replace(nom, gen)
			break

	return date_str


@register.filter
def get_item(dictionary, key):
	return dictionary.get(key)


@register.filter
def sum_total(items, field):
	"""Суммирует значения поля в списке словарей"""
	return sum(item.get(field, 0) for item in items)


@register.filter
def has_voted_winners(nominations):
	return any(nomination.get('winners') for nomination in nominations)


@register.filter
def custom_pluralize(value):
	if value % 10 == 1 and value % 100 != 11:
		return ""
	elif 2 <= value % 10 <= 4 and (value % 100 < 10 or value % 100 >= 20):
		return "а"
	else:
		return "ов"
