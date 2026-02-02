from django import forms
from .models import Banner


class BannerForm(forms.ModelForm):
	class Meta:
		model = Banner
		fields = '__all__'
		widgets = {
			'pages': forms.CheckboxSelectMultiple()
		}
