from allauth.account.forms import SignupForm
from allauth.account.models import EmailAddress
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Div, Row, HTML
from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from django.db.models.expressions import F
from django.forms import FileInput, ClearableFileInput
from django.forms.models import ModelMultipleChoiceField
from django.utils.html import format_html

from .logic import set_user_group
from .models import Exhibitors, Exhibitions, Portfolio, Image, MetaSEO, Nominations


class AccountSignupForm(SignupForm):
	""" Форма регистрации """
	username = (forms.CharField(
		label='Имя пользователя',
		widget=forms.TextInput(attrs={'placeholder': 'Имя пользователя (латиницей)'}))
	)
	email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'placeholder': 'Email адрес'}))
	first_name = forms.CharField(label='Имя', widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'}))
	last_name = forms.CharField(label='Фамилия', widget=forms.TextInput(attrs={'placeholder': 'Фамилия'}))
	exhibitor = forms.BooleanField(label="Участник выставки?", required=False)

	def __init__(self, *args, **kwargs):
		self.field_order = ['first_name', 'last_name', 'username', 'email', 'exhibitor', 'password1', 'password2', ]
		super().__init__(*args, **kwargs)
		self.fields["password2"].widget.attrs['placeholder'] = 'Пароль повторно'

	# class Meta:
	# 	model = User
	# 	fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'exhibitor',]

	# 	widgets = {
	# 		'first_name' : forms.TextInput(attrs={'placeholder': 'Имя'}),
	# 		'last_name' : forms.TextInput(attrs={'placeholder': 'Фамилия'}),
	# 	}

	# error_messages = {
	# 'duplicate_username': ("Имя пользователя уже существует")
	# }

	# def clean_username(self):
	# 	username = self.cleaned_data["username"]
	# 	if self.instance.username == username:
	# 		return username

	# 	try:
	# 		User._default_manager.get(username=username)
	# 	except User.DoesNotExist:
	# 		return username
	# 	raise forms.ValidationError(
	# 			self.error_messages['duplicate_username'],
	# 			code='duplicate_username',
	# 		)
	def save(self, request):
		# .save() returns a User object.
		user = super().save(request)
		user = set_user_group(request, user)

		return user


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


class CategoriesAdminForm(forms.ModelForm):
	class Meta:
		widgets = {
			'logo': forms.FileInput(attrs={'accept': '.svg'})
		}


class CustomSocialSignupForm(SocialSignupForm):
	""" Форма регистрации """
	first_name = forms.CharField(label='Имя', widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'}))
	last_name = forms.CharField(label='Фамилия', widget=forms.TextInput(attrs={'placeholder': 'Фамилия'}))

	username = forms.CharField(
		label='Имя пользователя',
		widget=forms.TextInput(attrs={'placeholder': 'Имя пользователя (уникальный ник)'})
	)
	email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'placeholder': 'Email адрес'}))
	exhibitor = forms.BooleanField(label="Участник выставки?", required=False)

	def __init__(self, *args, **kwargs):
		self.field_order = ['first_name', 'last_name', 'username', 'email', 'exhibitor', ]
		super().__init__(*args, **kwargs)

	def save(self, request):
		# .save() returns a User object.
		user = super().save(request)
		user = set_user_group(request, user)

		return user


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
	files = forms.ImageField(
		label='Фото',
		widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
		required=False
	)

	class Meta:
		model = Exhibitions
		fields = '__all__'
		# fields = ('meta_title','meta_description','meta_keywords')
		# exclude = ('slug',)
		# template_name = 'django/forms/widgets/checkbox_select.html'

		widgets = {
			# "exhibitors": forms.CheckboxSelectMultiple(attrs={'class': ''}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['files'].widget.attrs['multiple'] = True


class PortfolioAdminForm(MetaSeoFieldsForm, forms.ModelForm):
	# Это поле не сохраняется в модель, только для загрузки
	files = MultipleFileField(
		label='Фото',
		widget=MultipleFileInput(attrs={
			'class': 'form-control',
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

		STATUS_CHOICES = (
			(False, "Скрыт"),
			(True, "Доступен (по умолчанию)"),
		)

		widgets = {
			'cover': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
			'status': forms.Select(choices=STATUS_CHOICES),
		}


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


# def save(self, commit=True):
# 	# Здесь обрабатываешь загруженные files
# 	portfolio = super().save(commit=False)
# 	if commit:
# 		portfolio.save()
# 		files = self.cleaned_data.get('files')
# 		if files:
# 			# Сохраняешь в связанную модель Image
# 			for file in files:
# 				Image.objects.create(portfolio=portfolio, file=file)
# 	return portfolio


class PortfolioForm(PortfolioAdminForm):
	class Meta(PortfolioAdminForm.Meta):

		widgets = {
			'cover': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
			'categories': forms.CheckboxSelectMultiple(attrs={
				'class': 'form-check-input',
				'disabled': 'disabled'
			}),
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
			# Фильтруем номинации вручную через JavaScript
			self.fields['nominations'].queryset = Nominations.objects.all()

		if 'categories' in self.fields:
			# Настройка поля категорий
			self.fields['categories'].help_text = 'Категории автоматически определяются по выбранным номинациям'
			self.fields['categories'].label = 'Категории номинаций (автовыбор)'

		# Настройка поля выставки
		if 'exhibition' in self.fields:
			if self.is_editor:
				# В админке - динамическая фильтрация через JavaScript.
				self.fields['exhibition'].queryset = Exhibitions.objects.all()

			elif self.exhibitor:
				from django.utils.timezone import now

				# Для дизайнеров скрываем owner и status
				self.fields['owner'].initial = self.exhibitor
				self.fields['owner'].widget = forms.HiddenInput()
				self.fields['status'].widget = forms.HiddenInput()

				# Для дизайнеров фильтруем только активные и будущие выставки
				self.fields['exhibition'].queryset = Exhibitions.objects.filter(
					exhibitors=self.exhibitor,
					date_end__gte=now().date()
				).order_by('-date_start')
				self.fields['exhibition'].widget.attrs['disabled'] = True

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
					'<div class="mb-3"><h5>Участник: ' + (
						self.exhibitor.name if hasattr(self.exhibitor, 'name') else ''
					) + '</h5></div>'
				),
				Field(
					'owner',
					type="hidden"
				),  # Hidden field
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
					'files',
					css_class="form-control",
					wrapper_class="mb-2"
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


# def save(self, *args, **kwargs):
# 	instance = super().save(*args, **kwargs)
# 	if self.exhibitor:
# 		instance.categories.set(None)

# 	return instance


class ImageForm(forms.ModelForm):
	class Meta:
		model = Image
		fields = '__all__'
		widgets = {
			'file': MultipleFileInput(attrs={
				'class': 'form-control',
				'accept': 'image/*'
			})
		}

	# exclude = ('portfolio',)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['description'].widget = forms.Textarea(
			attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Описание'})


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
