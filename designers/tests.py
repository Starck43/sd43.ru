from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from exhibition.models import Exhibitors
from .forms import FeedbackForm
from .models import Designer

User = get_user_model()

LOCMEM_CACHE = {
	'default': {
		'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
	}
}


def feedback_data(**overrides):
	data = {
		'name': 'Иван',
		'from_email': 'ivan@example.com',
		'message': 'Здравствуйте! Хочу заказать проект.',
		'privacy_consent': 'on',
		'smart_token': 'test-token',
	}
	data.update(overrides)
	return data


@override_settings(DISABLE_CAPTCHA_IN_DEBUG=True)
class FeedbackFormTests(TestCase):
	def test_valid_form(self):
		form = FeedbackForm(feedback_data())
		self.assertTrue(form.is_valid(), form.errors)

	def test_honeypot_blocks_bot(self):
		form = FeedbackForm(feedback_data(website='http://spam.example'))
		self.assertFalse(form.is_valid())

	def test_privacy_consent_required(self):
		data = feedback_data()
		data.pop('privacy_consent')
		self.assertFalse(FeedbackForm(data).is_valid())


@override_settings(CACHES=LOCMEM_CACHE, DISABLE_CAPTCHA_IN_DEBUG=True)
class SendMessageViewTests(TestCase):
	def setUp(self):
		cache.clear()
		self.user = User.objects.create_user(
			username='designer-owner',
			email='owner@example.com',
			password='test-password',
		)
		# Без фонового потока оптимизации изображений: он конфликтует с тестовой БД
		with patch.object(Exhibitors, 'IMAGE_OPTIMIZE_ASYNC', False), \
				patch.object(Designer, 'IMAGE_OPTIMIZE_ASYNC', False):
			# Person.save() вызывает super().save() дважды, поэтому
			# objects.create(force_insert=True) даёт повторный INSERT
			self.exhibitor = Exhibitors(
				user=self.user,
				name='Владелец',
				slug='designer-owner',
			)
			self.exhibitor.save()
			self.designer = Designer(
				owner=self.exhibitor,
				slug='designer-site',
				status=2,
			)
			self.designer.save()
		self.url = reverse('designers:send-message', kwargs={'slug': self.designer.slug})

	def test_get_not_allowed(self):
		response = self.client.get(self.url, feedback_data())
		self.assertEqual(response.status_code, 405)

	def test_valid_post_sends_email(self):
		with patch('designers.views.send_email', return_value=True) as send:
			response = self.client.post(self.url, feedback_data())
		self.assertRedirects(response, '/success/', fetch_redirect_response=False)
		send.assert_called_once()

	def test_honeypot_blocks_submission(self):
		with patch('designers.views.send_email') as send:
			response = self.client.post(
				self.url,
				feedback_data(website='http://spam.example'),
			)
		self.assertRedirects(
			response,
			self.designer.get_absolute_url(),
			fetch_redirect_response=False,
		)
		send.assert_not_called()

	def test_privacy_consent_required(self):
		data = feedback_data()
		data.pop('privacy_consent')
		with patch('designers.views.send_email') as send:
			response = self.client.post(self.url, data)
		self.assertRedirects(
			response,
			self.designer.get_absolute_url(),
			fetch_redirect_response=False,
		)
		send.assert_not_called()