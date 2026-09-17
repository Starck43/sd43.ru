from django import forms
from .models import Designer

from exhibition.models import Portfolio
from exhibition.forms import MetaSeoFieldsForm, PrivacyConsentMixin


class DesignerForm(MetaSeoFieldsForm, forms.ModelForm):
	class Meta:
		model = Designer
		fields = '__all__'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance.id:
			self.fields['exh_portfolio'].queryset = Portfolio.objects.filter(owner=self.instance.owner,exhibition__isnull=False)
			self.fields['add_portfolio'].queryset = Portfolio.objects.filter(owner=self.instance.owner,exhibition__isnull=True)
			# self.fields['owner'].choices = [(owner.id, owner.name) for owner in owners]


class FeedbackForm(PrivacyConsentMixin, forms.Form):
	field_order = ['name', 'from_email', 'message', 'privacy_consent']

	name = forms.CharField(label='', required=True, widget=forms.TextInput(attrs={'placeholder': 'Ваше имя'}))
	#from_phone = forms.EmailField(label='Телефон', required=False, widget=forms.TextInput(attrs={'placeholder': 'Ваш номер для связи'}))
	from_email = forms.EmailField(label='', required=True, widget=forms.TextInput(attrs={'placeholder': 'Ваш почтовый ящик'}))
	message = forms.CharField(label='', required=True, widget=forms.Textarea(attrs={'placeholder': 'Сообщение', 'rows': 6}))

