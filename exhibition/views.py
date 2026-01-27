import math
from collections import defaultdict
from datetime import timedelta
from os import SEEK_END

from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from allauth.account.views import PasswordResetView
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import social_account_removed
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.files.uploadhandler import FileUploadHandler
from django.db import connection, OperationalError
from django.db.models import Q, OuterRef, Subquery, Avg, CharField, Case, When, Count
from django.dispatch import receiver
from django.forms import inlineformset_factory
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, HttpResponseRedirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
# from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from sorl.thumbnail import get_thumbnail
from watson.views import SearchMixin

from blog.models import Article
from designers.models import Designer
from rating.forms import RatingForm
from rating.models import Rating, Reviews
from .forms import PortfolioForm, ImageForm, ImageFormHelper, FeedbackForm, UsersListForm, DeactivateUserForm

from .utils import is_exhibitor_of_exhibition, is_jury_member
from .logic import send_email, send_email_async, set_user_group
from .mixins import ExhibitionYearListMixin, BannersMixin, MetaSeoMixin
from .models import *


def success_message(request):
	return HttpResponse('<h1>Сообщение отправлено!</h1><p>Спасибо за обращение</p>')


def registration_policy(request):
	""" Policy page """
	return render(request, 'policy.html')


def index(request):
	""" Main page """
	context = {
		'html_classes': ['home'],
		'organizers': Organizer.objects.all().only('sort', 'logo', 'name', 'description').order_by('sort', 'name'),
	}

	return render(request, 'index.html', context)


class ExhibitorsList(MetaSeoMixin, ExhibitionYearListMixin, ListView):
	""" Exhibitors view """
	model = Exhibitors
	queryset = Exhibitors.objects.all().order_by('name')
	template_name = 'exhibition/participants_list.html'

	def get_queryset(self):
		if self.kwargs.get('exh_year'):
			return self.queryset.prefetch_related('exhibitors_for_exh').filter(
				exhibitors_for_exh__slug=self.kwargs['exh_year']
			)
		else:
			return self.queryset.prefetch_related('exhibitors_for_exh')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', ]
		context['cache_timeout'] = 2592000

		return context


class PartnersList(MetaSeoMixin, ExhibitionYearListMixin, ListView):
	""" Partners view """
	model = Partners
	template_name = 'exhibition/partners_list.html'

	def get_queryset(self):
		if self.kwargs.get('exh_year'):
			q = Q(partners_for_exh__slug=self.kwargs['exh_year'])
		else:
			last_exh = Exhibitions.objects.values_list('slug', flat=True).first()
			q = ~Q(partners_for_exh__slug=last_exh)  # except last exhibition

		posts = self.model.objects.prefetch_related('partners_for_exh').filter(q)
		return posts

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', 'partners', ]
		context['cache_timeout'] = 2592000

		return context


class JuryList(MetaSeoMixin, ExhibitionYearListMixin, ListView):
	""" Jury view """
	model = Jury
	queryset = model.objects.all()
	template_name = 'exhibition/persons_list.html'

	def get_queryset(self):
		if self.kwargs.get('exh_year'):
			return self.queryset.prefetch_related('jury_for_exh').filter(
				jury_for_exh__slug=self.kwargs['exh_year']
			)
		else:
			return self.queryset

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', 'jury', ]
		context['cache_timeout'] = 2592000

		return context


class EventsList(MetaSeoMixin, ExhibitionYearListMixin, ListView):
	""" Events view """
	model = Events
	template_name = 'exhibition/participants_list.html'

	def get_queryset(self):
		if self.kwargs.get('exh_year'):
			posts = self.model.objects.filter(exhibition__slug=self.kwargs['exh_year']).order_by('title')
		else:
			posts = self.model.objects.all().order_by('-exhibition__slug', 'title')

		return posts

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['events', ]

		return context


class ExhibitionsList(MetaSeoMixin, BannersMixin, ListView):
	""" Exhibition view """
	model = Exhibitions

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['exhibitions', ]
		context['page_title'] = self.model._meta.verbose_name_plural

		return context


class WinnersList(MetaSeoMixin, ExhibitionYearListMixin, ListView):
	""" Winners view """
	model = Winners
	queryset = Winners.objects.all()
	template_name = 'exhibition/winners_list.html'

	def get_queryset(self):
		query = self.queryset.select_related(
			'nomination', 'exhibitor', 'exhibition', 'portfolio'
		).annotate(
			exh_year=F('exhibition__slug'),
			nomination_title=F('nomination__title'),
			exhibitor_name=F('exhibitor__name'),
			exhibitor_slug=F('exhibitor__slug'),
			project_id=F('portfolio__project_id'),
		).values(
			'exh_year', 'nomination_title', 'exhibitor_name', 'exhibitor_slug', 'project_id'
		).order_by('exhibitor_name', '-exh_year')

		if self.kwargs.get('exh_year'):
			return query.filter(exhibition__slug=self.kwargs['exh_year'])

		return query

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', 'winners']
		context['cache_timeout'] = 2592000

		return context


class CategoryList(MetaSeoMixin, BannersMixin, ListView):
	""" Categories (grouped Nominations) view """
	model = Categories
	template_name = 'exhibition/category_list.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['nominations', ]
		context['absolute_url'] = 'category'
		context['page_title'] = self.model._meta.verbose_name_plural
		context['cache_timeout'] = 2592000
		return context


class ProjectsList(MetaSeoMixin, BannersMixin, ListView):
	""" Projects view """
	model = Categories
	template_name = 'exhibition/projects_list.html'
	PAGE_SIZE = getattr(settings, 'PORTFOLIO_COUNT_PER_PAGE', 20)  # Количество выводимых записей на странице

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.object = None
		self.slug = None
		self.page = None
		self.is_next_page = None
		self.filters_group = None

	# использовано для миксина MetaSeoMixin, где проверяется self.object
	def setup(self, request, *args, **kwargs):
		super().setup(request, *args, **kwargs)
		self.slug = self.kwargs.get('slug')
		if self.slug:
			self.object = self.model.objects.get(slug=self.slug)

	def get_queryset(self):
		# Текущая страница для получения диапазона выборки записей
		self.page = int(self.page) if self.page else 1
		start_page = (self.page - 1) * self.PAGE_SIZE
		end_page = self.page * self.PAGE_SIZE

		query = Q(nominations__category__slug=self.slug)

		# Если выбраны опции фильтра
		if self.filters_group and self.filters_group[0] != '0':
			query.add(Q(attributes__in=self.filters_group), Q.AND)

		# Подзапрос для получения первого фото в портфолио
		subquery = Subquery(Image.objects.filter(portfolio=OuterRef('pk')).values('file')[:1])

		subquery2 = Subquery(Winners.objects.filter(
			portfolio_id=OuterRef('pk'),
			nomination__category__slug=self.slug
		).values('exhibition__slug')[:1])

		# Используем кастомный менеджер для фильтрации видимых проектов
		base_queryset = Portfolio.objects.get_visible_projects(self.request.user)

		posts = base_queryset.filter(
			Q(project_id__isnull=False) & query
		).distinct().prefetch_related('ratings').annotate(
			last_exh_year=F('exhibition__slug'),
			average=Avg('ratings__star'),
			win_year=subquery2,
			project_cover=Case(
				When(Q(cover__exact='') | Q(cover__isnull=True), then=subquery),
				default='cover',
				output_field=CharField()
			)
		).values(
			'id', 'project_id', 'project_cover', 'title', 'nominations__title',
			'last_exh_year', 'win_year', 'average', 'owner__name', 'owner__slug'
		).order_by(
			'-last_exh_year', '-win_year', '-average'
		)[start_page:end_page]

		self.is_next_page = False if len(posts) < self.PAGE_SIZE else True
		return posts

	def get(self, request, *args, **kwargs):
		self.page = self.request.GET.get('page', None)  # Параметр GET запроса ?page текущей страницы
		self.filters_group = self.request.GET.getlist('filter-group', None)
		# Выбранные опции checkbox в GET запросе (?nominations=[])

		if self.filters_group or self.page:
			default_quality = getattr(settings, 'THUMBNAIL_QUALITY', 85)
			admin_thumbnail_size = getattr(settings, 'ADMIN_THUMBNAIL_SIZE', [100, 100])
			admin_default_size = '%sx%s' % (admin_thumbnail_size[0], admin_thumbnail_size[1])
			admin_default_quality = getattr(settings, 'ADMIN_THUMBNAIL_QUALITY', 75)

			queryset = self.get_queryset()

			for i, q in enumerate(queryset):
				if q['project_cover']:
					thumb_mini = get_thumbnail(
						q['project_cover'],
						admin_default_size,
						crop='center',
						quality=admin_default_quality
					)
					thumb_320 = get_thumbnail(q['project_cover'], '320', quality=default_quality)
					thumb_576 = get_thumbnail(q['project_cover'], '576', quality=default_quality)
					queryset[i].update({
						'thumb_mini': str(thumb_mini),
						'thumb_xs': str(thumb_320),
						'thumb_sm': str(thumb_576),
						'thumb_xs_w': 320,
						'thumb_sm_w': 576
					})

			json_data = {
				'current_page': int(self.page or 1),
				'next_page': self.is_next_page,
				'projects_list': list(queryset),
				'projects_url': '/projects/',
				'media_url': settings.MEDIA_URL,
			}

			return JsonResponse(json_data, safe=False)
		else:
			# выполняется при загрузке первой страницы
			return super().get(request, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		# Отсортируем и сгруппируем словарь аттрибутов по ключу group
		# keyfunc = lambda x:x['group']
		# attributes = [list(data) for _, data in groupby(sorted(data, key=keyfunc), key=keyfunc)]

		# найдем аттрибуты для фильтра в портфолио, если они есть в текущей категории
		attributes = PortfolioAttributes.objects.prefetch_related('attributes_for_portfolio').filter(
			attributes_for_portfolio__nominations__category__slug=self.slug,
			group__isnull=False,
		).distinct()

		# Формирование групп аттрибутов фильтра
		attributes_dict = attributes.values('id', 'name', 'group')
		filter_attributes = defaultdict(list)
		for i, item in enumerate(attributes_dict):
			attributes_dict[i].update({'group_name': attributes[
				i].get_group_display()})  # {queryset_row}.get_group_display() - get choice field name
			filter_attributes[item['group']].append(attributes_dict[i])

		context['html_classes'] = ['projects', ]
		context['parent_link'] = '/category'
		context['absolute_url'] = self.slug
		context['object'] = self.object
		context['next_page'] = self.is_next_page
		context['filter_attributes'] = list(filter_attributes.values())
		context['cache_timeout'] = 86400  # one day
		return context


class ProjectsListByYear(ListView):
	""" Projects by year view """
	model = Portfolio
	template_name = 'exhibition/projects_by_year.html'

	def get_queryset(self):
		# Подзапрос для получения первого фото в портфолио
		subquery = Subquery(Image.objects.filter(portfolio=OuterRef('pk')).values('file')[:1])

		return self.model.objects.filter(
			Q(exhibition__slug=self.kwargs['exh_year']) & Q(project_id__isnull=False)
		).distinct().prefetch_related('ratings').annotate(
			project_cover=Case(
				When(Q(cover__exact='') | Q(cover__isnull=True), then=subquery),
				default='cover',
				output_field=CharField()
			)
		).values('id', 'title', 'owner__name', 'owner__slug', 'project_id', 'project_cover').order_by('owner__slug')

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['year'] = self.kwargs['exh_year']
		return context


class ExhibitorDetail(MetaSeoMixin, DetailView):
	""" Exhibitor detail """
	model = Exhibitors
	template_name = 'exhibition/participant_detail.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		base_queryset = Portfolio.objects.get_visible_projects(self.request.user)

		context['object_list'] = base_queryset.filter(
			owner__slug=self.kwargs['slug'],
			exhibition__isnull=False
		).annotate(
			exh_year=F('exhibition__slug'),
			win_year=Subquery(Winners.objects.filter(portfolio_id=OuterRef('pk')).values('exhibition__slug')[:1]),
			project_cover=Case(
				When(
					Q(cover__exact='') | Q(cover__isnull=True),
					then=Subquery(Image.objects.filter(portfolio_id=OuterRef('pk')).values('file')[:1])
				),
				default='cover',
				output_field=CharField()
			)
		).order_by('-exh_year')

		context['article_list'] = Article.objects.filter(
			owner=self.object.user
		).only('title').order_by('title') if self.object.user else None

		context['awards_list'] = Nominations.objects.prefetch_related('nomination_for_winner').filter(
			nomination_for_winner__exhibitor__slug=self.kwargs['slug']
		).annotate(
			exh_year=F('nomination_for_winner__exhibition__slug')
		).values('title', 'slug', 'exh_year').order_by('-exh_year')

		context['html_classes'] = ['participant']
		context['model_name'] = self.model.__name__.lower()
		context['cache_timeout'] = 86400

		return context


class JuryDetail(MetaSeoMixin, BannersMixin, DetailView):
	""" Jury detail """
	model = Jury
	template_name = 'exhibition/jury_detail.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participant', 'jury']
		context['model_name'] = self.model.__name__.lower()
		context['cache_timeout'] = 86400
		return context


class PartnerDetail(MetaSeoMixin, BannersMixin, DetailView):
	""" Partners detail """
	model = Partners
	template_name = 'exhibition/partner_detail.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participant', 'partner']
		context['model_name'] = self.model.__name__.lower()
		context['cache_timeout'] = 86400
		return context


class EventDetail(MetaSeoMixin, BannersMixin, DetailView):
	""" Event detail """
	model = Events
	template_name = 'exhibition/event_detail.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['event']
		context['model_name'] = self.model.__name__.lower()
		context['exh_year'] = self.kwargs['exh_year']
		return context


class ExhibitionDetail(MetaSeoMixin, BannersMixin, DetailView):
	""" Exhibitions detail """
	model = Exhibitions

	def get_object(self, queryset=None):
		slug = self.kwargs['exh_year']
		self.kwargs['id'] = 1
		try:
			q = self.model.objects.prefetch_related('events', 'gallery').get(slug=slug)
		except self.model.DoesNotExist:
			raise Http404
		return q

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		exhibition = self.object
		user = self.request.user
		is_jury = is_jury_member(user)

		# Определяем статус выставки
		context['exhibition_status'] = exhibition.status

		# Для upcoming выставок: участник может видеть только свои проекты
		# Для active/finished выставок: все видят все проекты
		context['show_projects'] = (
				user.is_staff or
				is_jury or
				context['exhibition_status'] in ['active', 'finished']
		)

		is_exhibitor = is_exhibitor_of_exhibition(user, exhibition)

		# Если выставка upcoming и пользователь не staff/жюри,
		# но является участником этой выставки - показываем только его проекты
		if context['exhibition_status'] == 'upcoming' and not (user.is_staff or is_jury):
			context['show_projects'] = is_exhibitor

		portfolios = Portfolio.objects.get_visible_projects(user).filter(
			exhibition=exhibition
		).select_related('owner').prefetch_related('nominations')

		# Если upcoming выставка и пользователь участник (но не staff/жюри)
		# показываем только его проекты
		if (
				context['exhibition_status'] == 'upcoming' and
				is_exhibitor and
				not (user.is_staff or is_jury)
		):
			portfolios = portfolios.filter(owner__user=user)

		# Для завершенной выставки - показываем победителей
		if context['exhibition_status'] == 'finished':
			context['win_nominations'] = exhibition.nominations.filter(
				nomination_for_winner__exhibition_id=exhibition.id
			).annotate(
				exhibitor_name=F('nomination_for_winner__exhibitor__name'),
				exhibitor_slug=F('nomination_for_winner__exhibitor__slug'),
				project_id=F('nomination_for_winner__portfolio__project_id'),
			).values('id', 'exhibitor_name', 'exhibitor_slug', 'project_id', 'title', 'slug')
		else:
			context['win_nominations'] = None

		# Загружаем проекты для показа
		if context['show_projects']:

			# Группируем проекты по номинациям вручную
			projects_by_nomination = {}
			for portfolio in portfolios:
				for nomination in portfolio.nominations.all():
					if nomination.id not in projects_by_nomination:
						projects_by_nomination[nomination.id] = []

					projects_by_nomination[nomination.id].append({
						'id': portfolio.id,
						'title': portfolio.title,
						'project_id': portfolio.project_id,
						'owner_slug': portfolio.owner.slug,
						'owner_name': portfolio.owner.name
					})

			context['projects_by_nomination'] = projects_by_nomination

		# Баннер слайдер
		banner_slider = []
		if exhibition.banner and exhibition.banner.width > 0:
			banner_slider.append(exhibition.banner)
			context['banner_height'] = f"{exhibition.banner.height / exhibition.banner.width * 100}%"

		# Для завершенной выставки добавляем фото победителей в слайдер
		if context['exhibition_status'] == 'finished' and context['win_nominations']:
			for nom in context['win_nominations']:
				cover = Image.objects.filter(
					portfolio__exhibition=exhibition.id,
					portfolio__nominations=nom['id'],
					portfolio__owner__slug=nom['exhibitor_slug'],
				).values('file').first()
				if cover:
					banner_slider.append(cover['file'])

		context['html_classes'] = ['exhibition']
		context['banner_slider'] = banner_slider
		context['events_title'] = Events._meta.verbose_name_plural
		context['gallery_title'] = Gallery._meta.verbose_name_plural
		context['last_exh'] = self.model.objects.only('slug').first().slug
		context['exh_year'] = self.kwargs['exh_year']
		context['model_name'] = self.model.__name__.lower()
		context['today'] = now().today()
		context['cache_timeout'] = 2592000

		return context


class WinnerProjectDetail(MetaSeoMixin, BannersMixin, DetailView):
	""" Winner project detail """
	model = Winners
	template_name = 'exhibition/nominations_detail.html'

	# slug_url_kwarg = 'name'

	def get_object(self, queryset=None):
		return self.model.objects.filter(
			exhibition__slug=self.kwargs['exh_year'],
			nomination__slug=self.kwargs['slug']
		).first()

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		portfolio = None
		if self.object:
			context['nomination'] = self.object.nomination
			context['exhibitors'] = None
			try:
				if self.object.portfolio:
					portfolio = Portfolio.objects.get(pk=self.object.portfolio.id)
				else:
					portfolio = Portfolio.objects.get(
						exhibition=self.object.exhibition,
						nominations=self.object.nomination,
						owner=self.object.exhibitor
					)
			except (Portfolio.DoesNotExist, Portfolio.MultipleObjectsReturned):
				pass

		else:
			context['nomination'] = Nominations.objects.get(slug=self.kwargs['slug']).only('title', 'description')
			context['exhibitors'] = Exhibitors.objects.prefetch_related('exhibitors_for_exh').filter(
				exhibitors_for_exh__slug=self.kwargs['exh_year']
			).only('name', 'slug')

		context['html_classes'] = ['project']
		context['portfolio'] = portfolio
		context['exh_year'] = self.kwargs['exh_year']
		context['parent_link'] = '/exhibition/%s/' % self.kwargs['exh_year']

		rate = 0
		if portfolio:
			stats = portfolio.get_rating_stats()
			rate = stats['average']

		if self.request.user.is_authenticated:
			context['user_score'] = Rating.objects.filter(
				portfolio=portfolio,
				user=self.request.user
			).values_list('star', flat=True).first()

		else:
			context['user_score'] = None

		context['average_rate'] = round(rate, 2)
		context['round_rate'] = math.ceil(rate)
		context['extra_rate_percent'] = int((rate - int(rate)) * 100)
		context['rating_form'] = RatingForm(
			initial={'star': int(rate)},
			user=self.request.user,
			score=context['user_score']
		)
		context['cache_timeout'] = 86400

		return context


class ProjectDetail(MetaSeoMixin, DetailView):
	""" Project detail """

	model = Portfolio
	context_object_name = 'portfolio'
	template_name = 'exhibition/portfolio_detail.html'
	# slug_url_kwarg = 'slug'

	def get_object(self, queryset=None):
		obj = None
		if self.kwargs.get('owner') and self.kwargs.get('project_id'):
			try:
				base_queryset = Portfolio.objects.get_visible_projects(self.request.user)
				obj = base_queryset.get(
					project_id=self.kwargs['project_id'],
					owner__slug=self.kwargs['owner']
				)
			except (self.model.DoesNotExist, Portfolio.DoesNotExist):
				pass

		return obj

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		context['victories'] = Winners.objects.filter(
			portfolio=self.object.id,
			exhibitor__slug=self.kwargs['owner']
		) if self.object else None

		if self.request.META.get('HTTP_REFERER') is None:
			nomination = self.object.nominations.filter(category__slug__isnull=False).first()
			if nomination and self.object:
				context['parent_link'] = '/category/%s/' % nomination.category.slug
			else:
				context['parent_link'] = '/category/'

		# Пересчитываем статистику рейтингов
		if self.object:
			ratings_aggregate = self.object.ratings.aggregate(
				average=Avg('star'),
				count=Count('id'),
				jury_average=Avg('star', filter=Q(is_jury_rating=True)),
				jury_count=Count('id', filter=Q(is_jury_rating=True))
			)

			rate = ratings_aggregate.get('average') or 0.0
			jury_avg = ratings_aggregate.get('jury_average') or 0.0
			jury_count = ratings_aggregate.get('jury_count') or 0
		else:
			rate = 0.0
			jury_avg = 0.0
			jury_count = 0

		# Проверяем текущую оценку пользователя
		user_rating = None
		if self.request.user.is_authenticated:
			user_rating = self.object.ratings.filter(user=self.request.user).first()
			context['user_score'] = user_rating.star if user_rating else None
		else:
			context['user_score'] = None

		context['is_jury'] = is_jury_member(self.request.user)
		context['jury_can_rate'] = False
		context['jury_avg'] = round(jury_avg, 2)
		context['jury_count'] = jury_count

		if self.object and self.object.exhibition and context['is_jury']:
			can_jury_rate, _ = Rating.can_jury_rate_now(self.object)
			context['jury_can_rate'] = can_jury_rate

		context['user_can_rate'] = False
		if self.request.user.is_authenticated:
			if context['is_jury']:
				context['user_can_rate'] = context['jury_can_rate']
			else:
				# Обычные пользователи И staff могут оценивать только после выставки
				can_rate = not context['user_score']
				if self.object and self.object.exhibition:
					rating_deadline = self.object.exhibition.date_end - timedelta(days=1)
					can_rate = can_rate and (now().date() > rating_deadline)

				context['user_can_rate'] = can_rate

		# Ключевое изменение: для жюри используем их личную оценку, вместо средней
		if context['is_jury'] and user_rating:
			# Жюри видят только свою оценку
			display_rate = user_rating.star
			context['round_rate'] = display_rate
			context['extra_rate_percent'] = 0  # Полные звезды
		else:
			# Обычные пользователи видят средний рейтинг
			display_rate = rate
			context['round_rate'] = math.ceil(rate)
			context['extra_rate_percent'] = int((rate - int(rate)) * 100)

		context['average_rate'] = round(display_rate, 2)

		context['rating_form'] = RatingForm(
			initial={'star': int(display_rate) if display_rate else 0},
			user=self.request.user,
			score=context['user_score']
		)

		context['html_classes'] = ['project']
		context['owner'] = self.kwargs['owner']
		context['is_owner'] = self.request.user.is_authenticated and self.object.owner.user == self.request.user
		context['project_id'] = self.kwargs['project_id']
		context['cache_timeout'] = 86400
		context['today'] = now().date()

		return context


def contacts(request):
	""" Отправка сообщения с формы обратной связи """
	if request.method == 'POST':
		# если метод POST, проверим форму и отправим письмо
		form = FeedbackForm(request.POST)
		if form.is_valid():
			template = render_to_string('contacts/confirm_email.html', {
				'name': form.cleaned_data['name'],
				'email': form.cleaned_data['from_email'],
				'message': form.cleaned_data['message'],
			})

			if send_email('Получено новое сообщение с сайта sd43.ru!', template):
				return redirect('/success/')

	else:
		form = FeedbackForm()

	context = {
		'html_classes': ['contacts'],
		'form': form,
	}
	return render(request, 'contacts.html', context)


class SearchSite(SearchMixin, ListView):
	""" Watson model's search """
	template_name = 'search_results.html'
	paginate_by = 15

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['search-result']
		# for result in self.object_list:
		# 	print(result)

		return context


class ProgressBarUploadHandler(FileUploadHandler):
	def receive_data_chunk(self, raw_data, start):
		return raw_data

	def file_complete(self, file_size):
		...


def get_nominations_categories(request):
	""" API endpoint для получения маппинга номинаций к категориям """
	nominations = Nominations.objects.select_related('category').all()
	mapping = {}
	for nom in nominations:
		if nom.category:
			mapping[str(nom.id)] = str(nom.category.id)

	return JsonResponse(mapping)


# views.py
@login_required
def get_nominations_for_exhibition(request):
	""" AJAX view для получения номинаций по выбранной выставке """
	exhibition_id = request.GET.get('exhibition_id')
	selected_ids = request.GET.get('selected', '').split(',')

	if exhibition_id:
		try:
			exhibition = Exhibitions.objects.get(id=exhibition_id)
			nominations = exhibition.nominations.all()

			nominations_data = []
			for nom in nominations:
				nominations_data.append({
					'id': nom.id,
					'title': nom.title,
					'selected': str(nom.id) in selected_ids
				})

			return JsonResponse({'nominations': nominations_data})
		except Exhibitions.DoesNotExist:
			return JsonResponse({'nominations': []})

	return JsonResponse({'nominations': []})


@login_required
def get_exhibitions_by_owner(request):
	"""AJAX view для получения выставок по выбранному участнику"""
	try:
		owner_id = request.GET.get('owner_id')

		if owner_id:
			try:
				owner = Exhibitors.objects.get(id=owner_id)
				exhibitions = owner.exhibitors_for_exh.all().order_by('-date_start')

				exhibitions_data = []
				for exh in exhibitions:
					exhibitions_data.append({
						'id': exh.id,
						'title': exh.title,
						'year': exh.date_start.year if exh.date_start else '',
						'date_start': exh.date_start.strftime('%d-%m-%Y') if exh.date_start else '',
						'slug': exh.slug
					})

				return JsonResponse({'exhibitions': exhibitions_data})

			except (Exhibitors.DoesNotExist, ValueError) as e:
				return JsonResponse({'exhibitions': []})

		return JsonResponse({'exhibitions': []})

	except Exception as e:
		return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_exhibitors_by_exhibition(request):
	"""AJAX view для получения участников по выбранной выставке"""
	exhibition_id = request.GET.get('exhibition_id')

	if exhibition_id:
		try:
			exhibition = Exhibitions.objects.get(id=exhibition_id)
			exhibitors = exhibition.exhibitors.all().values('id', 'name', 'user__first_name', 'user__last_name')

			exhibitors_data = []
			for exh in exhibitors:
				exhibitors_data.append({
					'id': exh['id'],
					'name': exh['name'] or f"{exh['user__first_name']} {exh['user__last_name']}".strip()
				})

			return JsonResponse({'exhibitors': exhibitors_data})
		except Exhibitions.DoesNotExist:
			return JsonResponse({'exhibitors': []})

	return JsonResponse({'exhibitors': []})


@csrf_exempt
@login_required
def portfolio_upload(request, **kwargs):
	""" Загрузка нового портфолио или редактирование существующего """

	# Проверка прав доступа
	# Разрешено: администраторам, редакторам (is_staff) и дизайнерам (группа Exhibitors)
	is_staff = request.user.is_staff
	is_exhibitor = request.user.groups.filter(name='Exhibitors').exists()

	if not is_staff and not is_exhibitor:
		from django.http import HttpResponseForbidden
		return HttpResponseForbidden('У вас нет прав для доступа к этой странице.')

	request.upload_handlers.insert(0, ProgressBarUploadHandler(request))

	pk = kwargs.pop('pk', None)
	if pk:
		portfolio = Portfolio.objects.filter(id=pk).first()
		owner = portfolio.owner
	else:
		portfolio = None
		owner = None

	# Определяем владельца портфолио
	if is_exhibitor and not is_staff:
		try:
			owner = Exhibitors.objects.get(user=request.user)

			# Проверка прав на редактирование существующего портфолио
			if portfolio:
				if portfolio.owner != owner:
					from django.http import HttpResponseForbidden
					return HttpResponseForbidden('Вы можете редактировать только свои портфолио.')

		except Exhibitors.DoesNotExist:
			from django.http import HttpResponseForbidden
			return HttpResponseForbidden('Профиль участника не найден.')

	is_ajax = request.is_ajax

	# Проверяем общий размер всех файлов
	if request.method == 'POST' and request.FILES:
		total_size = 0
		for file_key in request.FILES:
			for file in request.FILES.getlist(file_key):
				try:
					file.seek(0, SEEK_END)
					total_size += file.tell()
					file.seek(0)
				except (AttributeError, OSError):
					pass

		max_total_size = settings.MAX_UPLOAD_FILES_SIZE \
			if hasattr(settings, 'MAX_UPLOAD_FILES_SIZE') \
			else 100 * 1024 * 1024

		if total_size > max_total_size:
			if is_ajax:
				return JsonResponse({
					'status': 'error',
					'message': (
						f'Общий размер файлов ({total_size / (1024 * 1024):.1f} MB) '
						f'превышает лимит {max_total_size / (1024 * 1024)} MB'
					)
				}, status=400)
			else:
				messages.error(request, f'Общий размер файлов слишком большой!')

	form = PortfolioForm(owner=owner, is_staff=is_staff, instance=portfolio)
	inline_form_set = inlineformset_factory(Portfolio, Image, form=ImageForm, extra=0, can_delete=True)
	formset = inline_form_set(instance=portfolio)
	formset_helper = ImageFormHelper()

	if request.method == 'POST':
		form = PortfolioForm(request.POST, request.FILES, owner=owner, is_staff=is_staff, instance=portfolio)

		if form.is_valid():
			portfolio = form.save(commit=False)
			formset = inline_form_set(request.POST, request.FILES, instance=portfolio)

			if formset.is_valid():
				images = request.FILES.getlist('files')
				# Автоматически скрываем портфолио дизайнеров до модерации
				if not is_staff:
					portfolio.status = False
				portfolio.save(images=images)
				form.save_m2m()
				formset.save()

				nomination_ids = portfolio.nominations.values_list('id', flat=True)
				category_ids = Nominations.objects.filter(
					id__in=nomination_ids
				).exclude(category__isnull=True).values_list(
					'category_id', flat=True
				).distinct()

				# Обновить категории портфолио
				portfolio.categories.set(category_ids)

				context = {
					'user': '%s %s' % (request.user.first_name, request.user.last_name),
					'portfolio': portfolio,
					'files': images,
					'changed_fields': [],
					'new': True
				}
				if pk:
					context['changed_fields'] = form.changed_data
					context['new'] = False

				# Отправка email уведомления (раскомментировать при необходимости)
				# template = render_to_string('account/portfolio_upload_confirm.html', context)
				# send_email_async('%s портфолио на сайте sd43.ru!' % ('Внесены изменения в' if pk else 'Добавлено новое'), template)

				# Если это AJAX запрос, возвращаем JSON с URL для перенаправления
				if is_ajax:
					redirect_url = '/account'

					return JsonResponse({
						'status': 'success',
						'portfolio_id': portfolio.id,
						'location': redirect_url,
						'message': 'Портфолио успешно сохранено'
					})
				else:
					# Обычный запрос (не AJAX)
					if not pk:
						return render(request, 'success_upload.html', {'portfolio': portfolio, 'files': images})
					return redirect('/account')
			else:
				# Если formset невалиден, возвращаем ошибки
				print(formset.errors)
				if is_ajax:
					return JsonResponse({
						'status': 'error',
						'portfolio_id': portfolio.id,
						'errors': formset.errors,
						'message': 'Ошибка при загрузке изображений'
					}, status=400)
		else:
			# Если форма невалидна

			if is_ajax:
				return JsonResponse({
					'status': 'error',
					'portfolio_id': portfolio.id,
					'errors': form.errors,
					'message': 'Ошибка валидации формы'
				}, status=400)

	return render(
		request,
		'upload.html',
		{'form': form, "formset": formset, 'portfolio_id': pk, 'formset_helper': formset_helper}
	)


@login_required
def search_exhibitors(request):
	query = request.GET.get('q', '')
	exhibition_id = request.GET.get('exhibition_id')
	limit = int(request.GET.get('limit', 50))

	# Базовый queryset
	if exhibition_id:
		exhibitors = Exhibitors.objects.filter(
			exhibitors_for_exh__id=exhibition_id
		).select_related('user')
	else:
		exhibitors = Exhibitors.objects.all().select_related('user')

	# Применяем поиск если есть запрос
	if query:
		if len(query) < 3:
			# Для коротких запросов возвращаем пустой результат
			exhibitors = exhibitors.none()
		else:
			# Поиск при 3+ символах
			exhibitors = exhibitors.filter(
				Q(name__icontains=query) |
				Q(user__first_name__icontains=query) |
				Q(user__last_name__icontains=query)
			)

	# Применяем limit
	exhibitors = exhibitors[:limit]

	# Преобразуем в JSON
	results = [
		{
			'id': exh.id,
			'name': exh.name or f"{exh.user.first_name} {exh.user.last_name}".strip(),
		}
		for exh in exhibitors
	]

	return JsonResponse({'exhibitors': results})


@login_required
def account(request):
	""" Личный кабинет зарегистрированных пользователей """
	exhibitor = Exhibitors.objects.filter(user=request.user).first()
	jury = Jury.objects.filter(user=request.user).first()

	designer = None
	exh_portfolio = None
	add_portfolio = None
	victories = None
	achievements = None
	customers = None
	if exhibitor:
		exh_portfolio = Portfolio.objects.filter(owner=exhibitor, exhibition__isnull=False).annotate(
			exh_year=F('exhibition__slug'),
			project_cover=Case(
				When(
					Q(cover__exact='') | Q(cover__isnull=True),
					then=Subquery(Image.objects.filter(portfolio_id=OuterRef('pk')).values('file')[:1])
				),
				default='cover',
				output_field=CharField()
			)
		).order_by('-exh_year')

		try:
			designer = Designer.objects.get(owner=exhibitor)

			add_portfolio = designer.add_portfolio.all().annotate(
				project_cover=Case(
					When(
						Q(cover__exact='') | Q(cover__isnull=True),
						then=Subquery(Image.objects.filter(portfolio_id=OuterRef('pk')).values('file')[:1])
					),
					default='cover',
					output_field=CharField()
				)
			).order_by('title')

			victories = Nominations.objects.prefetch_related('nomination_for_winner').filter(
				nomination_for_winner__exhibitor=exhibitor).annotate(
				exh_year=F('nomination_for_winner__exhibition__slug')
			).values('title', 'slug', 'exh_year').order_by('-exh_year')

			achievements = designer.achievements.all().order_by('group')
		# customers = designer.customers.all()

		except Designer.DoesNotExist:
			pass

	articles = Article.objects.filter(owner=request.user).only('title').order_by('title')
	rates = Rating.objects.filter(user=request.user)
	reviews = Reviews.objects.filter(user=request.user)

	return render(request, 'account/base.html', {
		'exhibitor': exhibitor,
		'jury': jury,
		'designer': designer,
		'exh_portfolio': exh_portfolio,
		'add_portfolio': add_portfolio,
		'achievements': achievements,
		'victories': victories,
		'customers': customers,
		'articles': articles,
		'rates': rates,
		'reviews': reviews
	})


@staff_member_required
def send_reset_password_email(request):
	""" Sending reset password emails to exhibitors """
	if request.method == 'POST':
		form = UsersListForm(request.POST)
		if form.is_valid():
			users_email = request.POST.getlist('users') or None
			for email in users_email:
				request.POST = {
					'email': email,
					# 'csrfmiddlewaretoken': get_token(request) #HttpRequest()
				}
				# allauth reset password email send
				PasswordResetView.as_view()(request)

			# return render(request,'account/email/exhibitors/password_reset_key_message.html',self.data)
			return HttpResponse('<h1>Письма успешно отправлены!</h1>')
		else:
			return HttpResponse('<h1>Что-то пошло не так...</h1>')

	else:
		form = UsersListForm()

	return render(request, 'account/send_password_reset_email.html', {'form': form})


@login_required
# @method_decorator(csrf_exempt, name='dispatch')
def deactivate_user(request):
	""" Удаление аккаунта пользователя """
	if request.method == 'POST':
		form = DeactivateUserForm(request.POST)
		if form.is_valid():
			try:
				user_allauth = EmailAddress.objects.get(user__username=request.user.username)
				user_allauth.delete()
			except EmailAddress.DoesNotExist:
				pass

			try:
				social_account = SocialAccount.objects.get(user__username=request.user.username)
				social_account.delete()
				social_account_removed.send(
					sender=SocialAccount,
					request=request,
					socialaccount=social_account
				)
			except SocialAccount.DoesNotExist:
				pass

			# User Deactivation
			request.user.is_active = False
			request.user.save()
			# Log user out.
			# logout(request)
			# Give them a success message
			# messages.success(request, 'Аккаунт удален!')
			# return redirect(reverse('index'))
			return HttpResponseRedirect(reverse_lazy('account_logout'))

	else:
		form = DeactivateUserForm()

	return render(request, 'account/deactivation.html', {'form': form})


# dispatch_uid: some.unique.string.id.for.allauth.user_signed_up
@receiver(user_signed_up, dispatch_uid="new_user")
def user_signed_up_(request, user, **kwargs):
	""" Подслушаем событие регистрации нового пользователя и отправим письмо администратору """
	user = set_user_group(request, user)
	template = render_to_string('account/admin_email_confirm.html', {
		'name': '%s %s (%s)' % (user.first_name, user.last_name, user.username),
		'email': user.email,
		'group': list(user.groups.all().values_list('name', flat=True)),
	})
	send_email_async('Регистрация нового пользователя на сайте sd43.ru!', template)


class HealthCheckView(View):
	def get(self, request):
		# Проверяем подключение к БД
		try:
			with connection.cursor() as cursor:
				cursor.execute("SELECT 1")
			db_status = "connected"
		except OperationalError:
			db_status = "disconnected"

		return JsonResponse({
			"status": "healthy",
			"database": db_status,
			"service": "sferadesign"
		}, status=200 if db_status == "connected" else 503)
