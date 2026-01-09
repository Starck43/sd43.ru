import logging
import re
import unicodedata

from threading import Thread
from PIL import ImageFile, Image as Im
from io import BytesIO
from os import path, remove, SEEK_END
from sys import getsizeof

import PIL
from PIL import Image as PILImage, ImageOps
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import EmailMessage, BadHeaderError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.forms.widgets import ClearableFileInput
from django.contrib.auth.models import Group  # ,User

from sorl.thumbnail import get_thumbnail
from uuslug import slugify

ImageFile.LOAD_TRUNCATED_IMAGES = True

DEFAULT_SIZE = getattr(settings, 'DJANGORESIZED_DEFAULT_SIZE', [1500, 1024])
DEFAULT_QUALITY = getattr(settings, 'DJANGORESIZED_DEFAULT_QUALITY', 85)
DEFAULT_KEEP_META = getattr(settings, 'DJANGORESIZED_DEFAULT_KEEP_META', False)


def get_image_html(obj, width=50, height=None, css_class='', crop='center'):

	if not obj or not obj.name:
		return format_html('<img src="/media/site/no-image.png" width="{}" class="{}"/>', width, css_class)

	file_ext = path.splitext(obj.name)[1].lower()

	# SVG файлы
	if file_ext == '.svg':
		style = f'width: {width}px; height: {height}px;' if height else f'width: {width}px; height: auto;'
		return format_html(
			'<div style="display: inline-block; border: 1px solid #ddd; border-radius: 4px; padding: 2px; background: white;">'
			'<img src="{0}" style="{1}" class="{2}"/>'
			'</div>',
			obj.url, style, css_class
		)

	# Обычные изображения
	try:
		if height:
			thumb = get_thumbnail(obj, f'{width}x{height}', crop=crop, quality=85)
			return format_html(
				'<img src="{0}" width="{1}" height="{2}" class="{3}"/>',
				thumb.url, width, height, css_class
			)
		else:
			thumb = get_thumbnail(obj, f'{width}', quality=85)  # auto height
			return format_html('<img src="{0}" width="{1}" class="{2}"/>', thumb.url, width, css_class)

	except Exception:
		# Fallback
		if height:
			return format_html(
				'<img src="{0}" width="{1}" height="{2}" class="{3}"/>',
				obj.url, width, height, css_class
			)
		else:
			return format_html('<img src="{0}" width="{1}" class="{2}"/>', obj.url, width, css_class)


class MediaFileStorage(FileSystemStorage):

	def get_valid_name(self, name):
		filename, ext = path.splitext(name)
		name = slugify(filename) + ext.lower()
		return super().get_valid_name(name)

	def save(self, name, content, max_length=None):
		if not self.exists(name):
			return super().save(name, content, max_length)
		else:
			# prevent saving file on disk
			return name


def designers_upload_to(instance, filename):
	""" Designer files will be uploaded to MEDIA_ROOT/uploads/<author>/<filename> """
	return '{0}{1}/{2}'.format(
		settings.FILES_UPLOAD_FOLDER,
		instance.owner.slug.lower(),
		filename
	)


def portfolio_upload_to(instance, filename):
	""" portfolio files will be uploaded to MEDIA_ROOT/uploads/<author>/<exhibition>/<porfolio>/<filename> """
	exhibition_slug = instance.portfolio.exhibition.slug if instance.portfolio.exhibition else 'non-exhibition'
	return '{0}{1}/{2}/{3}/{4}'.format(
		settings.FILES_UPLOAD_FOLDER,
		instance.portfolio.owner.slug.lower(),
		exhibition_slug,
		instance.portfolio.slug,
		filename
	)


def cover_upload_to(instance, filename):
	""" portfolio cover will be uploaded to MEDIA_ROOT/uploads/<author>/<exhibition>/<porfolio>/<filename> """
	exhibition_slug = instance.exhibition.slug if instance.exhibition else 'non-exhibition'
	return '{0}{1}/{2}/{3}/{4}'.format(
		settings.FILES_UPLOAD_FOLDER,
		instance.owner.slug.lower(),
		exhibition_slug,
		instance.slug,
		filename
	)


def gallery_upload_to(instance, filename):
	""" gallery files will be uploaded to MEDIA_ROOT/gallery/<exh_year>/<filename> """
	return 'gallery/{0}/{1}'.format(instance.exhibition.slug.lower(), filename)


def image_resize(obj, size=None, uploaded_file=None):
	""" Adjusting image size before saving and converting to webp """
	if not obj:
		return

	if not size:
		size = DEFAULT_SIZE

	filename, ext = path.splitext(obj.name)

	# Проверяем, нужно ли конвертировать или изменять размер
	needs_processing = False
	if ext.lower() != '.webp':
		needs_processing = True
	elif uploaded_file:
		needs_processing = True
	elif hasattr(obj, 'width') and hasattr(obj, 'height'):
		if obj.width > size[0] or obj.height > size[1]:
			needs_processing = True

	if needs_processing:
		try:
			# Открываем изображение
			if hasattr(obj, 'path') and path.exists(obj.path):
				fn = obj.path
			else:
				fn = obj

			image = Im.open(fn)

			# Конвертируем RGBA в RGB для webp
			if image.mode in ('RGBA', 'LA', 'P'):
				background = Im.new('RGB', image.size, (255, 255, 255))
				if image.mode == 'P':
					image = image.convert('RGBA')
				background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
				image = background

			content_type = 'image/webp'
			image_format = 'WEBP'
			ext = '.webp'

			# Используем современный метод изменения размера для Pillow >= 10
			if int(PIL.__version__.split('.')[0]) >= 10:
				image = ImageOps.contain(image, size, method=PILImage.Resampling.LANCZOS)
			else:
				# Для старых версий Pillow
				image.thumbnail(size, Im.ANTIALIAS)

			# Сохраняем в буфер
			output = BytesIO()
			# Сохраняем метаданные если нужно
			if DEFAULT_KEEP_META:
				image.save(output, format=image_format, quality=DEFAULT_QUALITY, optimize=True)
			else:
				image.save(output, format=image_format, quality=DEFAULT_QUALITY, optimize=True, exif=b'')
			output.seek(0)

			# Создаем файл для загрузки
			file = InMemoryUploadedFile(
				file=output,
				field_name='ImageField',
				name=filename + ext,
				content_type=content_type,
				size=getsizeof(output),
				charset=None
			)

			if file:
				# Если файл уже существует, перезаписываем его
				if hasattr(obj, 'path') and path.exists(obj.path):
					with open(obj.path, 'wb+') as f:
						for chunk in file.chunks():
							f.write(chunk)
					return None
				# Иначе возвращаем новый файл
				return file
			return obj
		except (IOError, OSError) as e:
			logging.error('Ошибка открытия или обработки файла %s!' % e)
			raise ValidationError('Ошибка открытия или обработки файла %s!' % e)
	else:
		# Файл не требует обработки
		return None


def limit_file_size(file):
	""" Image file size validator """
	limit = settings.FILE_UPLOAD_MAX_MEMORY_SIZE \
		if hasattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE') \
		else 5 * 1024 * 1024

	try:
		# Получаем размер файла
		if hasattr(file, 'size'):
			file_size = file.size
		else:
			# Для файлов сохраненных на диск
			file.seek(0, SEEK_END)
			file_size = file.tell()
			file.seek(0)  # Возвращаем указатель в начало

		if file_size > limit:
			raise ValidationError(
				'Размер файла превышает лимит %s Мб. Рекомендуемый размер 1500x1024 пикс.' % (limit / (1024 * 1024))
			)
	except (AttributeError, OSError) as e:
		# Если не удалось определить размер
		logging.warning(f"Could not determine file size: {e}")
		# Можно пропустить или поднять ошибку в зависимости от требований
		pass


class CustomClearableFileInput(ClearableFileInput):
	template_name = 'admin/exhibition/widgets/file_input.html'


def send_email(subject, template, email_recipients=settings.EMAIL_RECIPIENTS):
	""" Sending email """
	email = EmailMessage(
		subject,
		template,
		settings.EMAIL_HOST_USER,
		email_recipients,
	)

	email.content_subtype = "html"
	email.html_message = True
	email.fail_silently = False

	try:
		email.send()
	except BadHeaderError:
		return HttpResponse('Ошибка в заголовке письма!')

	return True


class EmailThread(Thread):
	""" Async email sending class """

	def __init__(self, subject, template, email_recipients):
		self.subject = subject
		self.html_content = template
		self.recipient_list = email_recipients
		Thread.__init__(self)

	def run(self):
		return send_email(self.subject, self.html_content, self.recipient_list)


def send_email_async(subject, template, email_recipients=settings.EMAIL_RECIPIENTS):
	""" Sending email to recipients """
	EmailThread(subject, template, email_recipients).start()


def portfolio_upload_confirmation(images, request, obj):
	""" Отправим сообщение автору портфолио с уведомлением о добавлении фото """
	if images and obj.owner.user and obj.owner.user.email:  # new portfolio with images
		protocol = 'https' if request.is_secure() else 'http'
		host_url = "{0}://{1}".format(protocol, request.get_host())

		# Before email notification we need to get a list of uploaded thumbs [100x100]
		uploaded_images = []
		size = '%sx%s' % (settings.ADMIN_THUMBNAIL_SIZE[0], settings.ADMIN_THUMBNAIL_SIZE[1])
		for im in images:
			image = path.join(settings.FILES_UPLOAD_FOLDER, obj.owner.slug, obj.exhibition.slug, obj.slug, im.name)
			thumb = get_thumbnail(image, size, crop='center', quality=settings.ADMIN_THUMBNAIL_QUALITY)
			uploaded_images.append(thumb)

		subject = 'Добавление фотографий на сайте Сфера Дизайна'
		template = render_to_string('exhibition/new_project_notification.html', {
			'project': obj,
			'host_url': host_url,
			'uploaded_images': uploaded_images,
		})
		send_email_async(subject, template, [obj.owner.user.email])


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
		user.save()
	except Group.DoesNotExist:
		pass

	return user


def is_mobile(request):
	""" Return True if the request comes from a mobile device """
	import re

	agent = re.compile(r".*(iphone|mobile|androidtouch)", re.IGNORECASE)

	if agent.match(request.META['HTTP_USER_AGENT']):
		return True
	else:
		return False


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


def update_google_sitemap():
	...
