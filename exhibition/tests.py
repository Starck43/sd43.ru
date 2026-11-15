from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from exhibition.forms import ApplicationForm
from exhibition.models import Exhibitions

LOCMEM_CACHE = {
	'default': {
		'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
	}
}


def application_data(**overrides):
	data = {
		'name': 'Иван',
		'email': 'ivan@example.com',
		'phone': '+7 999 123-45-67',
		'message': 'Хочу участвовать в выставке',
		'privacy_consent': 'on',
		'smart_token': 'test-token',
	}
	data.update(overrides)
	return data


@override_settings(DISABLE_CAPTCHA_IN_DEBUG=True)
class ApplicationFormTests(TestCase):
	def test_valid_form(self):
		form = ApplicationForm(application_data())
		self.assertTrue(form.is_valid(), form.errors)

	def test_honeypot_blocks_bot(self):
		form = ApplicationForm(application_data(website='http://spam.example'))
		self.assertFalse(form.is_valid())

	def test_privacy_consent_required(self):
		data = application_data()
		data.pop('privacy_consent')
		self.assertFalse(ApplicationForm(data).is_valid())

	@override_settings(
		DISABLE_CAPTCHA_IN_DEBUG=False,
		YANDEX_CAPTCHA_CLIENT_KEY='test-client-key',
		YANDEX_CAPTCHA_SERVER_KEY='test-secret',
	)
	def test_missing_captcha_token(self):
		data = application_data()
		data.pop('smart_token')
		form = ApplicationForm(data)
		self.assertFalse(form.is_valid())
		self.assertIn('Токен капчи', str(form.non_field_errors()))

	@override_settings(
		DISABLE_CAPTCHA_IN_DEBUG=False,
		YANDEX_CAPTCHA_CLIENT_KEY='',
		YANDEX_CAPTCHA_SERVER_KEY='',
	)
	def test_unconfigured_captcha_does_not_block(self):
		data = application_data()
		data.pop('smart_token')
		form = ApplicationForm(data)
		self.assertTrue(form.is_valid(), form.errors)

	@override_settings(
		DISABLE_CAPTCHA_IN_DEBUG=False,
		YANDEX_CAPTCHA_CLIENT_KEY='test-client-key',
		YANDEX_CAPTCHA_SERVER_KEY='test-secret',
	)
	@patch('crm.captcha.requests.post')
	def test_captcha_rejected(self, post):
		post.return_value.status_code = 200
		post.return_value.content = b'{"status": "failed"}'
		form = ApplicationForm(application_data())
		self.assertFalse(form.is_valid())
		self.assertIn('Пройдите проверку безопасности', str(form.non_field_errors()))


@override_settings(CACHES=LOCMEM_CACHE, DISABLE_CAPTCHA_IN_DEBUG=True)
class ContactsViewTests(TestCase):
	url = reverse('exhibition:contacts-url')

	def setUp(self):
		cache.clear()

	def test_valid_application_sends_email(self):
		with patch('exhibition.views.send_email', return_value=True) as send:
			response = self.client.post(self.url, application_data())
		self.assertRedirects(response, '/success/', fetch_redirect_response=False)
		send.assert_called_once()

	def test_honeypot_blocks_submission(self):
		with patch('exhibition.views.send_email') as send:
			response = self.client.post(self.url, application_data(website='http://spam.example'))
		self.assertEqual(response.status_code, 200)
		send.assert_not_called()

	def test_rate_limit(self):
		with patch('exhibition.views.send_email', return_value=True):
			for _ in range(5):
				self.client.post(self.url, application_data())
			response = self.client.post(self.url, application_data())
		self.assertEqual(response.status_code, 429)

	@override_settings(
		DISABLE_CAPTCHA_IN_DEBUG=False,
		YANDEX_CAPTCHA_CLIENT_KEY='test-client-key',
	)
	def test_captcha_widget_rendered(self):
		response = self.client.get(self.url)
		self.assertContains(response, 'smartcaptcha.yandexcloud.net/captcha.js')
		self.assertContains(response, 'id_smart_token')


@override_settings(CACHES=LOCMEM_CACHE, DISABLE_CAPTCHA_IN_DEBUG=True)
class ExhibitionDetailTests(TestCase):
    def test_non_ended_exhibition_detail_opens_for_public(self):
        """Новая (незавершённая) выставка открывается для публики без 500.

        Раньше при show_projects=False переменная projects_by_nomination не
        попадала в контекст, в шаблоне резолвилась в строку, и фильтр
        get_item падал с AttributeError: 'str' object has no attribute 'get'.
        """
        exhibition = Exhibitions.objects.create(
            title='Текущая выставка',
            slug='test-exhibition-current',
            date_start=timezone.now() - timedelta(days=5),
            date_end=timezone.now() + timedelta(days=30),
        )
        url = reverse('exhibition:exhibition-detail-url', kwargs={'exh_year': exhibition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)