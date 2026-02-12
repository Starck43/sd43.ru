from datetime import date

from allauth.account.forms import SignupForm
from allauth.account.models import EmailAddress
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Div, Row, HTML
from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery, Max
from django.db.models.expressions import F
from django.forms import ClearableFileInput, SelectMultiple
from django.forms.models import ModelMultipleChoiceField
from django.utils.html import format_html

from crm.captcha import CaptchaValidationMixin
from .logic import is_image_file
from .models import Exhibitors, Exhibitions, Portfolio, Image, MetaSEO, Nominations, Gallery
from .utils import set_user_group


class MultipleFileInput(forms.ClearableFileInput):
	"""Кастомный виджет для множественной загрузки файлов"""
	allow_multiple_selected = True


class MultipleFileField(forms.FileField):
	"""Кастомное поле для множественной загрузки файлов"""

	def __init__(self, *args, **kwargs):
		kwargs.setdefault("widget", MultipleFileInput())
		super().__init__(*args, **kwargs)

	def clean(self, data, initial=None):
		single_file_clean = super().clean
		if isinstance(data, (list, tuple)):
			result = [single_file_clean(d, initial) for d in data]
		else:
			result = [single_file_clean(data, initial)]

		return result


class CustomClearableFileInput(ClearableFileInput):
	def __init__(self, attrs=None):
		attrs = attrs or {}
		attrs['accept'] = 'image/*'
		super().__init__(attrs)


class DisabledSelectMultiple(SelectMultiple):
	"""SelectMultiple с disabled опциями"""

	def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
		option = super().create_option(name, value, label, selected, index, subindex, attrs)

		if 'disabled' not in option['attrs']:
			option['attrs']['disabled'] = True
		return option


class CategoriesAdminForm(forms.ModelForm):
	class Meta:
		widgets = {
			'logo': forms.FileInput(attrs={'accept': '.svg'})
		}


class DeactivateUserForm(forms.Form):
	deactivate = forms.BooleanField(
		label='Удалить?',
		help_text='Пожалуйста, поставьте галочку, если желаете удалить аккаунт',
		required=True
	)


class MetaSeoForm(forms.ModelForm):
	model = forms.ModelChoiceField(
		label='Раздел',
		queryset=MetaSEO.get_content_models(),
	)

	post_id = forms.ModelChoiceField(
		label='Запись раздела',
		widget=forms.Select(),
		queryset=None,
		required=False
	)

	class Meta:
		model = MetaSEO
		fields = '__all__'
		widgets = {
			'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Описание'}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		if not self.instance.pk:
			choices = [[None, '--------']] + [
				[obj.pk, obj.model_class()._meta.verbose_name_plural] for obj in
				MetaSEO.get_content_models()
			]
			self.fields['model'].choices = choices
			self.fields['post_id'].widget = forms.HiddenInput()  # скрыть поле post_id

		else:
			if self.instance.post_id:
				self.fields['model'].disabled = True

			if self.instance.model:
				model = MetaSEO.get_model(self.instance.model.model)
				queryset = model.objects.all()
				self.fields['post_id'].queryset = queryset
				choices = [[None, '--------']] + list((x.id, x.__str__()) for x in queryset)
				self.fields['post_id'].choices = choices

	def clean(self):
		cleaned_data = super().clean()
		if self.cleaned_data['post_id']:
			self.cleaned_data['post_id'] = self.cleaned_data['post_id'].id
		return cleaned_data


class MetaSeoFieldsForm(forms.ModelForm):
	meta_title = forms.CharField(
		label='Мета заголовок',
		widget=forms.TextInput(attrs={'style': 'width:100%;box-sizing: border-box;'}),
		required=False
	)
	meta_description = forms.CharField(
		label='Мета описание',
		widget=forms.TextInput(attrs={'style': 'width:100%;box-sizing: border-box;'}),
		required=False
	)
	meta_keywords = forms.CharField(
		label='Ключевые фразы', widget=forms.TextInput(
			attrs={'style': 'width:100%;box-sizing: border-box;', 'placeholder': 'введите ключевые слова через запятую'}
		),
		required=False
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		model_name = self._meta.model.__name__.lower()
		self.meta_model = ContentType.objects.get(model=model_name)
		self.meta = None
		if self.instance.pk:
			try:
				self.meta = MetaSEO.objects.get(model=self.meta_model, post_id=self.instance.id)
				self.fields['meta_title'].initial = self.meta.title
				self.fields['meta_description'].initial = self.meta.description
				self.fields['meta_keywords'].initial = self.meta.keywords
			except MetaSEO.DoesNotExist:
				pass

	def save(self, *args, **kwargs):
		instance = super().save(*args, **kwargs)
		meta_changed = any(s in ['meta_title', 'meta_keywords', 'meta_description'] for s in self.changed_data)
		meta_title = self.cleaned_data['meta_title']
		meta_description = self.cleaned_data['meta_description']
		meta_keywords = self.cleaned_data['meta_keywords']
		if meta_changed:
			if self.meta:
				self.meta.title = meta_title
				self.meta.description = meta_description
				self.meta.keywords = meta_keywords
				self.meta.save()
			else:
				MetaSEO.objects.create(
					model=self.meta_model,
					post_id=instance.id,
					title=meta_title,
					description=meta_description,
					keywords=meta_keywords
				)

		return instance


class ExhibitionsForm(MetaSeoFieldsForm, forms.ModelForm):
	files = MultipleFileField(
		label='Фото с выставки',
		widget=MultipleFileInput(attrs={
			'class': 'form-control multiple-files-control',
			'accept': 'image/*',
		}),
		required=False,
		help_text='Общий размер загружаемых фото не должен превышать %s Мб' % round(
			settings.MAX_UPLOAD_FILES_SIZE / 1024 / 1024)
	)

	class Meta:
		model = Exhibitions
		fields = '__all__'


class PortfolioAdminForm(MetaSeoFieldsForm, forms.ModelForm):
	files = MultipleFileField(
		label='Фото',
		widget=MultipleFileInput(attrs={
			'class': 'form-control multiple-files-control',
			'accept': 'image/*',
		}),
		required=False,
		help_text='Общий размер загружаемых фото не должен превышать %s Мб' % round(
			settings.MAX_UPLOAD_FILES_SIZE / 1024 / 1024)
	)

	class Meta:
		model = Portfolio
		fields = (
			'owner', 'exhibition', 'categories', 'nominations', 'attributes', 'title', 'description', 'cover', 'files',
			'status',
		)

	def clean(self):
		cleaned_data = super().clean()
		owner = cleaned_data.get('owner')
		exhibition = cleaned_data.get('exhibition')

		# Проверяем, что выставка доступна участнику
		if owner and exhibition:
			if not owner.exhibitors_for_exh.filter(id=exhibition.id).exists():
				self.add_error(
					'exhibition',
					f'Участник "{owner.name}" не зарегистрирован на выставку "{exhibition.title}". '
					f'Сначала добавьте участника на выставку.'
				)

		return cleaned_data


class PortfolioForm(PortfolioAdminForm):
	class Meta(PortfolioAdminForm.Meta):

		STATUS_CHOICES = (
			(False, "Скрыт"),
			(True, "Доступен (по умолчанию)"),
		)

		widgets = {
			'cover': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
			'categories': forms.CheckboxSelectMultiple(attrs={
				'class': 'form-check-input',
				'disabled': True
			}),
			'status': forms.Select(choices=STATUS_CHOICES),
			# 'attributes': forms.CheckboxSelectMultiple(attrs={'class': 'form-group'}),
		}

	def __init__(self, *args, **kwargs):
		self.exhibitor = kwargs.pop('owner', None)
		self.is_editor = kwargs.pop('is_staff', False)

		super().__init__(*args, **kwargs)

		if 'cover' in self.fields:
			self.fields['cover'].widget.attrs.update({
				'class': 'form-control cover-upload',
				'data-preview': 'cover-preview'
			})

		if 'nominations' in self.fields and hasattr(self.fields['nominations'], 'queryset'):
			self.fields['nominations'].queryset = Nominations.objects.all()

		if 'categories' in self.fields:
			# Настройка поля категорий
			self.fields['categories'].help_text = 'Категории автоматически определяются по выбранным номинациям'
			self.fields['categories'].label = 'Категории номинаций (автовыбор)'

		if 'exhibition' in self.fields:
			if self.is_editor:
				# Редакторы видят все выставки
				self.fields['exhibition'].queryset = Exhibitions.objects.all()

			elif self.exhibitor:
				# Дизайнеры
				self.fields['owner'].initial = self.exhibitor
				self.fields['owner'].widget = forms.HiddenInput()
				self.fields['status'].widget = forms.HiddenInput()

				today = date.today()
				# Получаем выставки, где зарегистрирован дизайнер и они еще не начались
				available_exhibitions = Exhibitions.objects.filter(
					exhibitors=self.exhibitor,
					date_start__gt=today
				).order_by('-date_start')

				self.fields['exhibition'].queryset = available_exhibitions

				# Проверяем, есть ли уже выставка у портфолио
				if self.instance and self.instance.pk and self.instance.exhibition:
					# Выставка уже есть - делаем поле readonly
					self.fields['exhibition'].widget.attrs.update({
						'class': 'form-control disabled-field',
						'disabled': True,
					})
					self.fields['exhibition'].help_text = 'Выставка уже определена'

					# Убедимся, что текущая выставка в queryset
					if self.instance.exhibition not in available_exhibitions:
						# Если текущая выставка не в списке доступных, добавляем ее
						self.fields['exhibition'].queryset = available_exhibitions | Exhibitions.objects.filter(
							id=self.instance.exhibition_id
						)

					if self.instance and self.instance.pk:
						current_nominations = self.instance.nominations.values_list('id', flat=True)
						self.initial['nominations'] = list(current_nominations)

					# Делаем поле disabled
					self.fields['nominations'].widget.attrs.update({
						'class': 'form-control disabled-multiselect',
						'style': 'pointer-events: none; opacity: 0.7;',
						'disabled': True,
					})
					self.fields['nominations'].help_text = 'Номинации недоступны для изменения'

				else:
					# Если есть только одна доступная выставка, выбираем ее по умолчанию
					if available_exhibitions.count() == 1:
						self.fields['exhibition'].initial = available_exhibitions.first()
						self.fields['exhibition'].widget.attrs.update({
							'class': 'form-control single-option',
							'readonly': True  # только для просмотра, но значение отправляется
						})

	def save(self, commit=True):
		portfolio = super().save(commit=False)

		# Для дизайнеров восстанавливаем выставку если поле disabled
		if not self.is_editor and self.exhibitor and portfolio.pk:
			# Получаем оригинальное значение из БД
			original_portfolio = Portfolio.objects.get(pk=portfolio.pk)
			if original_portfolio.exhibition:
				portfolio.exhibition = original_portfolio.exhibition

		if commit:
			portfolio.save()
			self.save_m2m()

		return portfolio

	@property
	def helper(self):
		helper = FormHelper()
		helper.form_tag = False

		# Для редакторов показываем владельцев проектов, для дизайнера - скрываем
		if self.is_editor:
			layout_fields = [
				Field(
					'owner',
					css_class="form-control",
					placeholder="Выберите участника",
					wrapper_class="mb-2"
				),
				Field(
					'exhibition',
					css_class="form-control",
					placeholder="Выберите выставку",
					wrapper_class="mb-2"
				),
				Field(
					'nominations',
					wrapper_class='field-nominations mb-2 hidden',
					css_class="form-control"
				),
				Field(
					'categories',
					wrapper_class='field-categories mb-2 hidden',
					template='crispy_forms/multiple_checkboxes.html',
					field_class='categories-checkboxes'
				),
				Field(
					'title',
					css_class="form-control",
					placeholder="Название проекта",
					wrapper_class="mb-2"
				),
				Field(
					'description',
					css_class="form-control",
					placeholder="Описание проекта",
					rows=4,
					wrapper_class="mb-2"
				),
				Field(
					'cover',
					template='crispy_forms/cover_field.html',
					wrapper_class="mb-2"
				),
				Field(
					'files',
					css_class="form-control",
					wrapper_class="mb-2"
				),
				Field(
					'status',
					css_class="form-control",
					placeholder="Статус",
					wrapper_class="mb-2"
				),
				Field(
					'attributes',
					wrapper_class='field-attributes d-none mb-2',
					css_class="form-control"
				),
			]
		else:
			layout_fields = [
				HTML(
					'<div class="mb-3"><h4>Участник: ' + (
						self.exhibitor.name if hasattr(self.exhibitor, 'name') else ''
					) + '</h4></div>'
				),
				Field(
					'owner',
					type="hidden"
				),
				Field(
					'exhibition',
					css_class="form-control",
					placeholder="Выберите выставку",
					wrapper_class="mb-2"
				),
				Field(
					'nominations',
					wrapper_class='field-nominations mb-2 hidden',
					css_class="form-control"
				),
				Field(
					'categories',
					wrapper_class='field-categories mb-2 hidden',
					template='crispy_forms/multiple_checkboxes.html',
					field_class='categories-checkboxes'
				),
				Field(
					'title',
					css_class="form-control",
					placeholder="Название проекта",
					wrapper_class="mb-2"
				),
				Field(
					'description',
					css_class="form-control",
					placeholder="Описание проекта",
					rows=4,
					wrapper_class="mb-2"
				),
				Field(
					'cover',
					template='crispy_forms/cover_field.html',
					wrapper_class="mb-2"
				),
				Field(
					'files',
					css_class="form-control",
					wrapper_class="mb-2"
				),
				Field(
					'status',
					type="hidden"
				),  # Hidden field
			]

		# Добавляем SEO поля только для администратора
		if self.is_editor:
			layout_fields.append(
				Div(
					HTML('<div class="card-header">СЕО описание для поисковых систем</div>'),
					Div(
						Field(
							'meta_title',
							css_class="form-control",
							placeholder="Заголовок",
							wrapper_class="mb-2"
						),
						Field(
							'meta_description',
							css_class="form-control",
							placeholder="Описание",
							rows=2,
							wrapper_class="mb-2"
						),
						Field(
							'meta_keywords',
							css_class="form-control",
							placeholder="ключевые слова",
							wrapper_class="mb-2"
						),
						css_class='card-body'
					),
					css_class="card mt-2 mb-4",
				)
			)

		helper.layout = Layout(*layout_fields)
		return helper


class ImageForm(forms.ModelForm):
	class Meta:
		model = Image
		fields = '__all__'
		widgets = {
			'file': MultipleFileInput(attrs={
				'class': 'form-control',
				'accept': 'image/*',
			})
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['description'].widget = forms.Textarea(
			attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Описание'})


class ImageInlineForm(forms.ModelForm):
	class Meta:
		widgets = {
			'file': forms.FileInput(attrs={
				'accept': 'image/*',
				'required': False,
			}),
			'sort': forms.HiddenInput(),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		if not self.instance.pk:
			self.empty_permitted = True

		# Автоматически устанавливаем сортировку для новых форм
		if not self.instance.pk and not self.initial.get('sort'):
			# Устанавливаем максимальное значение + 1
			if 'portfolio' in self.initial:
				portfolio_id = self.initial['portfolio']
				max_sort = Image.objects.filter(portfolio_id=portfolio_id).aggregate(
					Max('sort')
				)['sort__max']
				self.initial['sort'] = (max_sort or 0) + 1
			else:
				self.initial['sort'] = 1

			if 'exhibition' in self.initial:
				exhibition_id = self.initial['exhibition']
				max_sort = Gallery.objects.filter(exhibition_id=exhibition_id).aggregate(
					Max('sort')
				)['sort__max']
				self.initial['sort'] = (max_sort or 0) + 1
			else:
				self.initial['sort'] = 1

	def clean_file(self):
		file = self.cleaned_data.get('file')

		# Новая форма без файла — разрешено (empty-form)
		if not file and not self.instance.pk:
			return None

		if file:
			if not is_image_file(file):
				raise ValidationError(
					"Поддерживаются только файлы изображений: JPG, JPEG, PNG, GIF, WebP"
				)

			if file.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
				max_size_mb = settings.FILE_UPLOAD_MAX_MEMORY_SIZE / 1024 / 1024
				raise ValidationError(
					f"Размер файла не должен превышать {max_size_mb:.1f} MB"
				)

		return file


class ImageInlineFormSet(forms.BaseInlineFormSet):
	def clean(self):
		super().clean()

		# Фильтруем только реально заполненные формы
		valid_forms = []
		for i, form in enumerate(self.forms):
			# Если форма имеет файл ИЛИ это существующая запись
			if ('file' in form.cleaned_data and form.cleaned_data['file']) or form.instance.pk:
				valid_forms.append(form)
			elif form.has_changed():
				# Если форма изменена, но без файла - ошибка
				if not form.instance.pk and 'file' not in form.errors:
					form.add_error('file', 'Для новой записи файл обязателен.')
				valid_forms.append(form)

		total_size = 0
		for form in self.forms:
			if form.cleaned_data.get('DELETE'):
				continue

			if form.cleaned_data:
				file = form.cleaned_data.get('file')
				if file and hasattr(file, 'size'):
					total_size += file.size

		# Проверка общего размера всех файлов
		if hasattr(settings, 'MAX_UPLOAD_FILES_SIZE') and total_size > settings.MAX_UPLOAD_FILES_SIZE:
			max_size_mb = settings.MAX_UPLOAD_FILES_SIZE / 1024 / 1024
			raise ValidationError(
				f"Общий размер всех файлов не должен превышать {max_size_mb} MB"
			)


class ImageFormHelper(FormHelper):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.form_tag = False
		self.include_media = False
		self.disable_csrf = True
		self.layout = Layout(
			Div(
				HTML('<div class="card-header">Фото {{forloop.counter}}</div>'),
				Row(
					Div(
						Field('file', template='crispy_forms/image.html'),
						css_class="image-container"
					),
					Div(
						Field('title', css_class="form-control", placeholder="Название фото"),
						Field('description', css_class="form-control", placeholder="Описание фото", rows=3),
						Field('sort', css_class="form-control", placeholder="Порядок"),
						Field('DELETE', wrapper_class='form-check form-check-inline'),
						css_class="meta"
					),
					css_class="card-body"
				),
				css_class="portfolio-image card d-flex-column mb-2"
			)
		)


class PrepareWinnersForm(forms.Form):
	exhibition = forms.ModelChoiceField(
		queryset=Exhibitions.objects.all(),
		label='Выставка'
	)


class FeedbackForm(forms.Form):
	name = forms.CharField(
		label='Имя', required=True, widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'})
	)
	from_email = forms.EmailField(
		label='E-mail', required=True,
		widget=forms.TextInput(attrs={'placeholder': 'Ваш почтовый ящик'})
	)
	message = forms.CharField(
		label='Сообщение', required=True,
		widget=forms.Textarea(attrs={'placeholder': 'Сообщение'})
	)


class UserMultipleModelChoiceField(ModelMultipleChoiceField):
	""" Mixin: Переопределение отображения списка пользователей в UsersListForm """

	def label_from_instance(self, obj):
		if obj.verified is not None:
			if obj.verified:
				email_status = '<img src="/static/admin/img/icon-yes.svg">'
			else:
				email_status = '<img src="/static/admin/img/icon-no.svg">'
		else:
			email_status = ''

		return format_html(
			'<b>{0}</b> [{1}] </span><span>{2}</span><span>{3}</span>', obj.name, obj.user_email,
			obj.last_exh or '', format_html(email_status)
		)


class UsersListForm(forms.Form):
	""" Вывод списка пользователей в рассылке сброса паролей"""
	subquery = Subquery(Exhibitions.objects.filter(exhibitors=OuterRef('pk')).values('slug')[:1])
	subquery2 = Subquery(EmailAddress.objects.filter(user_id=OuterRef('user_id')).values('verified')[:1])
	users = UserMultipleModelChoiceField(
		label=format_html(
			'{}<span>{}</span><span>{}</span>',
			'Имя [Email]',
			'Последняя выставка',
			'Верификация'
		),
		widget=forms.CheckboxSelectMultiple(),
		queryset=Exhibitors.objects.distinct().filter(user__is_active=True).annotate(
			user_email=F('user__email'),
			last_exh=subquery,
			verified=subquery2,
		).order_by('-last_exh', 'user_email', 'name'),
		to_field_name="user_email"
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)


class CustomSocialSignupForm(SocialSignupForm):
	"""Форма регистрации через соцсети с капчей"""

	first_name = forms.CharField(label='Имя', widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'}))
	last_name = forms.CharField(label='Фамилия', widget=forms.TextInput(attrs={'placeholder': 'Фамилия'}))
	# username = forms.CharField(
	# 	label='Имя пользователя',
	# 	widget=forms.TextInput(attrs={'placeholder': 'Имя пользователя (уникальный ник)'})
	# )
	email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'placeholder': 'Email адрес'}))
	exhibitor = forms.BooleanField(label="Участник выставки?", required=False)

	def __init__(self, *args, **kwargs):
		self.field_order = ['first_name', 'last_name', 'email', 'exhibitor']
		super().__init__(*args, **kwargs)
		# Сохраняем request для получения IP
		if 'request' in kwargs:
			self.request = kwargs['request']

	def save(self, request):
		user = super().save(request)
		user = set_user_group(request, user)
		#  user.is_active = True
		user.save()
		return user


class AccountSignupForm(CaptchaValidationMixin, SignupForm):
	"""Форма обычной регистрации с капчей"""

	first_name = forms.CharField(label='Имя', widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'}))
	last_name = forms.CharField(label='Фамилия', widget=forms.TextInput(attrs={'placeholder': 'Фамилия'}))
	email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'placeholder': 'Email адрес'}))
	exhibitor = forms.BooleanField(label="Участник выставки?", required=False)
	smart_token = forms.CharField(widget=forms.HiddenInput(), required=False)

	def __init__(self, *args, **kwargs):
		self.field_order = [
			'first_name', 'last_name', 'email', 'exhibitor',
			'password1', 'password2', 'smart_token'
		]
		super().__init__(*args, **kwargs)
		self.fields["password2"].widget.attrs['placeholder'] = 'Пароль повторно'
		# Сохраняем request для получения IP
		if 'request' in kwargs:
			self.request = kwargs['request']

	def save(self, request):
		user = super().save(request)
		user = set_user_group(request, user)
		user.save()
		return user
