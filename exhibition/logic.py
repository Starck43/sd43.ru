import logging
from dataclasses import dataclass
from glob import glob

from threading import Thread
from PIL import ImageFile, Image as Im
from io import BytesIO
from os import path, SEEK_END
from sys import getsizeof

import PIL
from PIL import Image as PILImage, ImageOps
from django.core.files.base import ContentFile
from django.db.models.fields.files import ImageFieldFile
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import EmailMessage, BadHeaderError
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from sorl.thumbnail import get_thumbnail
from uuslug import slugify

logger = logging.getLogger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True

DEFAULT_SIZE = getattr(settings, 'DJANGORESIZED_DEFAULT_SIZE', [1500, 1024])
DEFAULT_QUALITY = getattr(settings, 'DJANGORESIZED_DEFAULT_QUALITY', 85)
DEFAULT_KEEP_META = getattr(settings, 'DJANGORESIZED_DEFAULT_KEEP_META', False)
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'tiff', 'webp'}

@dataclass
class ProcessedImage:
	buffer: BytesIO
	format: str
	extension: str
	content_type: str


def process_image(
		file,
		*,
		max_size=None,
		quality=DEFAULT_QUALITY,
		force_format='WEBP'
) -> ProcessedImage:
	"""
	Функция оптимизации изображений.
	- resize
	- convert to webp
	- strip alpha
	"""

	if max_size is None:
		max_size = DEFAULT_SIZE

	if force_format is None:
		try:
			img = PILImage.open(file)
			original_format = img.format
			img.close()

			if original_format and original_format.upper() in ['JPEG', 'PNG', 'GIF']:
				force_format = original_format.upper()
			else:
				force_format = 'JPEG'  # fallback
		except:
			force_format = 'JPEG'

	image = PILImage.open(file)

	width, height = image.size
	max_width, max_height = max_size

	if image.mode in ('RGBA', 'LA', 'P'):
		image = ImageOps.exif_transpose(image)
		background = PILImage.new('RGB', image.size, (255, 255, 255))
		if image.mode == 'P':
			image = image.convert('RGBA')
		background.paste(image, mask=image.split()[-1])
		image = background

	# Если изображение МЕНЬШЕ max_size - НЕ изменяем размер
	if width > max_width or height > max_height:
		image = ImageOps.contain(
			image,
			max_size,
			method=PILImage.Resampling.LANCZOS
		)

	output = BytesIO()
	image.save(
		output,
		format=force_format,
		quality=quality,
		method=6,
		optimize=True
	)
	output.seek(0)

	return ProcessedImage(
		buffer=output,
		format=force_format,
		extension='.' + force_format.lower(),
		content_type=f'image/{force_format.lower()}'
	)


def optimize_image_fields_async(instance, field_names, to_webp=True):
	pk = instance.pk
	model = instance.__class__

	def worker():
		obj = model.objects.get(pk=pk)

		updated = False
		for field_name in field_names:
			field = getattr(obj, field_name, None)
			if not field or not field.name:
				continue

			# Проверяем, что это изображение (не SVG и т.д.)
			ext = path.splitext(field.name)[1].lower()
			if ext not in ALLOWED_IMAGE_EXTENSIONS:
				continue

			try:
				field.seek(0)  # перематываем на начало
				result = process_image(
					field,
					force_format='WEBP' if to_webp else 'JPEG'
				)

				# Сохраняем обработанный файл в таблицу
				new_name = field.name.rsplit('.', 1)[0] + result.extension
				field.save(
					new_name,
					ContentFile(result.buffer.read()),
					save=False
				)
				updated = True

			except Exception as e:
				logger.error(f"Error optimizing {field_name}: {e}")

		if updated:
			obj.save(update_fields=field_names)

	Thread(target=worker, daemon=True).start()


class MediaFileStorage(FileSystemStorage):
	OPTIMIZE_ON_SAVE = True

	def __init__(
			self,
			image_size=None,
			quality=None,
			file_format='WEBP',
			base_url=None,
			location=None,
			**kwargs
	):
		super().__init__(location=location, base_url=base_url, **kwargs)
		self.image_size = image_size or DEFAULT_SIZE
		self.quality = quality or DEFAULT_QUALITY
		self.file_format = file_format

	def get_available_name(self, name, max_length=None):
		upload_folder, filename = path.split(name)
		filename, extension = path.splitext(filename.lower())
		ext = extension

		filename = slugify(filename, separator='-', save_order=True)

		# Проверяем, есть ли файл с таким именем
		root_dir = self.path(upload_folder)
		existing_files = glob(f"{filename}.*", root_dir=root_dir)
		if existing_files:
			# Если файл есть, добавляем индекс
			index = 2
			while glob(f"{filename}-{index}.*", root_dir=root_dir):
				index += 1
			filename = f"{filename}-{index}"

		name = path.join(upload_folder, filename + ext)
		return name

	def _save(self, name, content):
		if (
				self.OPTIMIZE_ON_SAVE and
				content.content_type.startswith('image/') and
				content.content_type != 'image/svg+xml'
		):

			try:
				content.seek(0)

				# Обрабатываем изображение
				result = process_image(
					content,
					max_size=self.image_size,
					quality=self.quality,
					force_format=self.file_format
				)

				content = ContentFile(result.buffer.read())
				name = name.rsplit('.', 1)[0] + result.extension

			except Exception as e:
				logger.error(f"Error optimizing image in storage: {e}")
				content.seek(0)

		return super()._save(name, content)


def designers_upload_to(instance, filename):
	""" Designer files will be uploaded to MEDIA_ROOT/uploads/<author>/<filename> """
	return '{0}{1}/{2}'.format(
		settings.FILES_UPLOAD_FOLDER,
		instance.owner.slug.lower(),
		filename
	)


def portfolio_upload_to(instance, filename):
	""" portfolio files will be uploaded to MEDIA_ROOT/uploads/<author>/<exhibition>/<portfolio>/<filename> """
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


def get_absolute_path(relative_path):
	base_dir = path.dirname(path.dirname(path.abspath(__file__)))
	absolute_path = path.join(base_dir, relative_path)
	return absolute_path


def get_image_url(obj: ImageFieldFile, request=None):
	if is_file_exist(obj):
		return request.build_absolute_uri(obj.url) if request else obj.url

	return None


def is_file_exist(obj):
	if not obj:
		return False

	if isinstance(obj, str):
		return path.isfile(get_absolute_path(obj))

	try:
		# Если файл сохранён — у него есть путь
		if hasattr(obj, 'path'):
			return path.isfile(obj.path)
		else:
			# Если это строка пути, пробуем через storage
			return default_storage.exists(obj)
	except NotImplementedError:
		# Например, если используется RemoteStorage, который не реализует .path
		return obj and default_storage.exists(obj.name)


def is_image_file(obj, file_ext=None):
	if not obj:
		return False

	# UploadedFile или строка
	if hasattr(obj, 'content_type'):
		content_type = getattr(obj, 'content_type', '')
		return content_type.startswith('image/')
	elif hasattr(obj, 'name'):
		name = obj.name
	elif isinstance(obj, str):
		name = obj
	else:
		return False

	_, ext = path.splitext(name.lower())
	if not ext:
		return False

	ext = ext.lstrip('.')

	if file_ext:
		return ext == file_ext.lower().lstrip('.')

	return ext in ALLOWED_IMAGE_EXTENSIONS


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
