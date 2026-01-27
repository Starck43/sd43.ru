from django import forms
from .models import Rating, Reviews
from exhibition.utils import is_jury_member


def stars_choices():
	return [(6 - r, r) for r in range(1, 6)]


class RatingForm(forms.ModelForm):
	"""Форма добавления рейтинга"""
	star = forms.ChoiceField(widget=forms.RadioSelect(), choices=stars_choices)

	class Meta:
		model = Rating
		fields = ("star",)

	def __init__(self, *args, **kwargs):
		self.user = kwargs.pop('user', None)
		self.score = kwargs.pop('score', None)
		self.can_rate = kwargs.pop('can_rate', False)

		super().__init__(*args, **kwargs)

		if not self.user.is_authenticated or (self.score and not is_jury_member(self.user)):
			self.fields['star'].widget.attrs['disabled'] = True


class ReviewForm(forms.ModelForm):
	"""Форма отзывов"""

	class Meta:
		model = Reviews
		fields = ("message",)
