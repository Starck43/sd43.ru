import logging
import math
from collections import defaultdict
from os import SEEK_END

from allauth.account.models import EmailAddress
from allauth.account.views import PasswordResetView
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import social_account_removed
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.files.uploadhandler import FileUploadHandler
from django.db import connection, OperationalError
from django.db.models import Q, OuterRef, Subquery, Avg, CharField, Case, When, Count, Max
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
from watson.views import SearchMixin

from blog.models import Article
from designers.models import Designer
from rating.forms import RatingForm
from rating.models import Rating, Reviews
from .forms import PortfolioForm, ImageForm, ImageFormHelper, FeedbackForm, UsersListForm, DeactivateUserForm
from .logic import send_email
from .mixins import BannersMixin, MetaSeoMixin, ExhibitionsYearsMixin, ProjectsLazyLoadMixin
from .models import *
from .services import ProjectsQueryService
from .utils import is_exhibitor_of_exhibition, is_jury_member, get_exhibitor_for_user, can_rate_portfolio

logger = logging.getLogger(__name__)


def success_message(request):
	return HttpResponse('<h1>Сообщение отправлено!</h1><p>Спасибо за обращение</p>')


def registration_policy(request):
	""" Policy page """
	return render(request, 'policy.html')


def index(request):
	""" Main page """
	context = {
		'html_classes': ['home'],
		'organizers': Organizer.objects.all().order_by('sort', 'name'),
	}

	return render(request, 'index.html', context)


class ExhibitorsList(MetaSeoMixin, ExhibitionsYearsMixin, ListView):
	""" Exhibitors view """
	model = Exhibitors
	queryset = Exhibitors.objects.annotate(
		latest_exh_date=Max('exhibitors_for_exh__date_start')
	).order_by('-latest_exh_date', 'name')

	template_name = 'exhibition/participants_list.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', ]
		context['cache_timeout'] = 2592000
		return context


class PartnersList(MetaSeoMixin, ExhibitionsYearsMixin, ListView):
	""" Partners view """
	model = Partners
	queryset = Partners.objects.annotate(
		latest_exh_date=Max('partners_for_exh__date_start')
	).order_by('-latest_exh_date', 'name')

	template_name = 'exhibition/partners_list.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', 'partners', ]
		context['cache_timeout'] = 2592000

		return context


class JuryList(MetaSeoMixin, ExhibitionsYearsMixin, ListView):
	""" Jury view """
	model = Jury
	queryset = Jury.objects.annotate(
		latest_exh_date=Max('jury_for_exh__date_start')
	).order_by('-latest_exh_date', 'name')

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


class EventsList(MetaSeoMixin, ExhibitionsYearsMixin, ListView):
	""" Events view """
	model = Events
	template_name = 'exhibition/participants_list.html'

	def get_queryset(self):
		if self.is_all_years_page:
			posts = self.model.objects.all().order_by('-exhibition__slug', 'title')
		elif self.kwargs.get('exh_year'):
			posts = self.model.objects.filter(exhibition__slug=self.kwargs['exh_year']).order_by('title')
		else:
			posts = self.model.objects.none()

		return posts

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['events', ]
		return context


class WinnersList(MetaSeoMixin, ExhibitionsYearsMixin, ListView):
	""" Winners view """
	model = Winners
	queryset = Winners.objects.all()
	template_name = 'exhibition/winners_list.html'

	def get_queryset(self):
		queryset = self.queryset

		if self.is_all_years_page:
			queryset = queryset.all()
		elif self.kwargs.get('exh_year'):
			queryset = queryset.filter(exhibition__slug=self.kwargs['exh_year'])
		else:
			return Winners.objects.none()

		# Добавляем аннотации и выбор полей
		return queryset.select_related(
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

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['participants', 'winners']
		context['cache_timeout'] = 2592000

		return context


class ExhibitionsList(MetaSeoMixin, BannersMixin, ListView):
	""" Exhibition view """
	model = Exhibitions

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['exhibitions', ]
		context['page_title'] = self.model._meta.verbose_name_plural
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


class ProjectsList(ProjectsLazyLoadMixin, MetaSeoMixin, BannersMixin, ListView):
	""" Projects view """
	model = Categories
	template_name = 'exhibition/projects_list.html'

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
		self.object = self.model.objects.filter(slug=self.slug).first()

	@staticmethod
	def build_filter_attributes(attributes):
		attributes_values = list(attributes.values('id', 'name', 'group'))
		grouped = defaultdict(list)

		for idx, item in enumerate(attributes_values):
			item['group_name'] = attributes[idx].get_group_display()
			grouped[item['group']].append(item)

		return list(grouped.values())

	def get_filter_cache_key(self):
		return f'portfolio:filters:{self.slug}'

	def get_filter_attributes(self):
		cache_key = self.get_filter_cache_key()
		cached = cache.get(cache_key)

		if cached is not None:
			return cached

		attributes = PortfolioAttributes.objects.prefetch_related(
			'attributes_for_portfolio'
		).filter(
			attributes_for_portfolio__nominations__category__slug=self.slug,
			group__isnull=False,
		).distinct()

		grouped = self.build_filter_attributes(attributes)

		cache.set(cache_key, grouped, 86400)  # сутки
		return grouped

	def apply_filters(self, queryset):
		query = Q(nominations__category__slug=self.slug)

		if self.filters_group and self.filters_group[0] != '0':
			query &= Q(attributes__in=self.filters_group)

		return queryset.filter(
			Q(project_id__isnull=False) & query
		).distinct()

	def get_queryset(self):
		qs = Portfolio.objects.get_visible_projects(self.request.user)

		qs = qs.filter(
			project_id__isnull=False,
			nominations__category__slug=self.slug
		).distinct()

		if self.filters_group and self.filters_group[0] != '0':
			qs = qs.filter(attributes__in=self.filters_group)

		qs = ProjectsQueryService.get_cover_with_rating(qs).annotate(
			last_exh_year=F('exhibition__slug'),
			win_year=Subquery(
				Winners.objects.filter(
					portfolio_id=OuterRef('pk'),
					nomination__category__slug=self.slug
				).values('exhibition__slug')[:1]
			),
		)

		return qs.values(
			'id', 'project_id', 'project_cover', 'title',
			'last_exh_year', 'win_year', 'average',
			'owner__name', 'owner__slug'
		).order_by('-last_exh_year', '-win_year', '-average')

	def get(self, request, *args, **kwargs):
		self.init_pagination(request)
		self.filters_group = request.GET.getlist('filter-group')

		if self.filters_group or 'page' in request.GET:
			qs = self.paginate_queryset(self.get_queryset())
			return self.build_projects_response(qs)

		return super().get(request, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		context.update({
			'html_classes': ['projects'],
			'parent_link': '/category',
			'absolute_url': self.slug,
			'action_url': reverse('exhibition:projects-list-url', kwargs={'slug': self.slug}),
			'object': self.object,
			'next_page': self.is_next_page,
			'filter_attributes': self.get_filter_attributes(),
			'cache_timeout': 86400,
		})

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


class ExhibitorDetail(ProjectsLazyLoadMixin, MetaSeoMixin, DetailView):
	""" Exhibitor detail """
	model = Exhibitors
	template_name = 'exhibition/participant_detail.html'

	def get_projects_queryset(self):
		return ProjectsQueryService.get_cover_with_rating(
			Portfolio.objects.get_visible_projects(self.request.user).filter(
				owner__slug=self.kwargs['slug'],
				exhibition__isnull=False
			)
		).annotate(
			exh_year=F('exhibition__slug'),
			win_year=Subquery(
				Winners.objects.filter(
					portfolio_id=OuterRef('pk')
				).values('exhibition__slug')[:1]
			)
		).values(
			'id', 'project_id', 'project_cover', 'title',
			'exh_year', 'win_year', 'average',
			'owner__name', 'owner__slug'
		).order_by('-exh_year')

	def get(self, request, *args, **kwargs):
		self.init_pagination(request)

		if 'page' in request.GET:
			qs = self.paginate_queryset(self.get_projects_queryset())
			return self.build_projects_response(qs)

		return super().get(request, **kwargs)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)

		projects = self.paginate_queryset(self.get_projects_queryset())

		context.update({
			'object_list': projects,
			'next_page': self.is_next_page,
			'action_url': reverse(
				'exhibition:exhibitor-detail-url',
				kwargs={'slug': self.kwargs['slug']}
			),
			'model_name': self.model._meta.model_name.lower(),
			'cache_timeout': 86400,
		})
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
		is_exhibitor = get_exhibitor_for_user(user)

		context['is_exhibitor'] = is_exhibitor_of_exhibition(user, exhibition)
		context['exhibition_ended'] = exhibition.is_exhibition_ended
		context['win_nominations'] = None

		# Проекты доступны для:
		# 1. участников, жюри и сотрудников - всегда
		# 2. для остальных - после завершения текущей выставки
		context['show_projects'] = (
				user.is_staff or
				is_jury or
				is_exhibitor or
				context['exhibition_ended']
		)

		# Загружаем проекты для показа
		if context['show_projects']:
			portfolios = Portfolio.objects.get_visible_projects(user, exhibition=exhibition)

			# Группируем проекты по номинациям вручную
			projects_by_nomination = {}
			for portfolio in portfolios:
				for nomination in portfolio.nominations.all():
					if nomination.id not in projects_by_nomination:
						projects_by_nomination[nomination.id] = []

					projects_by_nomination[nomination.id].append({
						'id': portfolio.id,
						'title': portfolio.title,
						'cover': portfolio.get_cover,
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
		if context['exhibition_ended']:
			context['win_nominations'] = exhibition.nominations.filter(
				nomination_for_winner__exhibition_id=exhibition.id
			).annotate(
				exhibitor_name=F('nomination_for_winner__exhibitor__name'),
				exhibitor_slug=F('nomination_for_winner__exhibitor__slug'),
				project_id=F('nomination_for_winner__portfolio__project_id'),
			).values('id', 'exhibitor_name', 'exhibitor_slug', 'project_id', 'title', 'slug')

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
		context['today'] = timezone.now()
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

		total_rate = 0
		if portfolio:
			stats = portfolio.get_rating_stats()
			total_rate = stats['average']

		if self.request.user.is_authenticated:
			context['user_score'] = Rating.objects.filter(
				portfolio=portfolio,
				user=self.request.user
			).values_list('star', flat=True).first()

		else:
			context['user_score'] = None

		context['average_rate'] = round(total_rate, 1)
		context['round_rate'] = math.ceil(total_rate)
		context['extra_rate_percent'] = int((total_rate - int(total_rate)) * 100)
		context['rating_form'] = RatingForm(
			initial={'star': int(total_rate)},
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

	def get_object(self, queryset=None):
		if self.kwargs.get('owner') and self.kwargs.get('project_id'):
			try:
				base_queryset = Portfolio.objects.get_visible_projects(self.request.user)
				return base_queryset.get(
					project_id=self.kwargs['project_id'],
					owner__slug=self.kwargs['owner']
				)
			except (self.model.DoesNotExist, Portfolio.DoesNotExist):
				raise Http404("Проект не найден")

		raise Http404("Проект не найден")

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		user = self.request.user

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
			ratings_aggregate = self.object.get_rating_stats()

			rate = ratings_aggregate.get('average') or 0.0
			jury_avg = ratings_aggregate.get('jury_average') or 0.0
			jury_count = ratings_aggregate.get('jury_count') or 0
			context['round_rate'] = 0

			if rate:
				context['average_rate'] = round(rate, 1)
				context['round_rate'] = math.ceil(rate)
				context['extra_rate_percent'] = int((rate - int(rate)) * 100)

		else:
			rate = 0.0
			jury_avg = 0.0
			jury_count = 0
			context['round_rate'] = 0
			context['extra_rate_percent'] = 0

		context['exhibition'] = self.object.exhibition
		if self.object and self.object.exhibition:
			context['exhibition_ended'] = self.object.exhibition.is_exhibition_ended
			context['jury_voting_active'] = self.object.exhibition.is_jury_voting_active
			context['jury_deadline'] = self.object.exhibition.jury_deadline

		context['is_jury'] = is_jury_member(user)
		context['jury_avg'] = round(jury_avg, 2)
		context['jury_count'] = jury_count

		# Определяем, может ли пользователь голосовать
		res = can_rate_portfolio(user, self.object, context['is_jury'])
		context['user_can_rate'], context['rate_message'], context['user_rate'] = res

		# Определяем, как показывать средний рейтинг
		# 1. Сотрудники всегда видят среднюю оценку
		# 2. Жюри видят свою оценку если могут еще голосовать, иначе видят среднюю
		if context['is_jury'] and self.object.exhibition.is_jury_voting_active:
			rate = context['user_rate']
			context['round_rate'] = context['user_rate']
			context['average_rate'] = 0
			context['show_average'] = False
		else:
			context['show_average'] = True

		# Форма рейтинга
		context['rating_form'] = RatingForm(
			initial={'star': int(rate) if rate else 0},
			user=user,
			score=context['round_rate']
		)

		context['html_classes'] = ['project']
		context['owner'] = self.kwargs['owner']
		context['is_owner'] = user and user.is_authenticated and self.object.owner.user == user
		context['project_id'] = self.kwargs['project_id']
		context['cache_timeout'] = 86400
		context['today'] = timezone.now()

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
def deactivate_user(request):
	if request.method == 'POST':
		form = DeactivateUserForm(request.POST)
		if form.is_valid():
			request.user.is_active = False
			request.user.save()

			return redirect('account_logout')
	else:
		form = DeactivateUserForm()

	return render(request, 'account/deactivation.html', {'form': form})


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
	portfolio = None
	owner = None
	if pk:
		try:
			portfolio = Portfolio.objects.get(id=pk)
			owner = portfolio.owner
		except Portfolio.DoesNotExist:
			raise Http404

	# Определяем владельца портфолио
	if is_exhibitor and not is_staff:
		try:
			owner = Exhibitors.objects.get(user=request.user, user__is_active=True)

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
				# Автоматически скрываем добавленное портфолио дизайнеров до модерации
				if not pk and not is_staff:
					portfolio.status = False

				portfolio.save(images=images)

				if is_staff or is_exhibitor and not pk:
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
				logger.error(formset.errors)
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


def __404__(request, exception):
	"""Кастомный обработчик 404"""
	from django.http import HttpResponseNotFound

	# Для статики - простой 404
	if request.path.startswith('/static/') or request.path.startswith('/media/'):
		return HttpResponseNotFound()

	try:
		context = {
			'title': '404 - Страница не найдена',
			'message': 'Запрашиваемая страница не существует или недоступна.',
		}

		# Для авторизованных пользователей - ссылка на их профиль
		if request.user.is_authenticated:
			try:
				exhibitor = Exhibitors.objects.get(user=request.user)
				context['user_profile_url'] = exhibitor.get_absolute_url()
				context['has_user_profile'] = True
			except Exhibitors.DoesNotExist:
				context['has_user_profile'] = False

		# Только для путей проектов
		if request.path.startswith('/projects/'):
			try:
				parts = request.path.strip('/').split('/')
				if len(parts) >= 3:
					project = Portfolio.objects.get(
						owner__slug=parts[1],
						project_id=parts[2].replace('project-', '')
					)
					context['project'] = project
					context['exhibitions_url'] = '/exhibitions/'

					# URL автора проекта
					context['author_profile_url'] = project.owner.get_absolute_url()

					if project.exhibition:
						context['exhibitions_url'] = project.exhibition.get_absolute_url()
						today = timezone.now()
						if today < project.exhibition.date_start:
							context['title'] = 'Проект временно закрыт для публичного доступа'
							context['message'] = f'Проект участвует в будущей выставке "{project.exhibition.title}".'
							context['reason'] = 'future_exhibition'
							context['available_date'] = project.exhibition.date_end

						elif not project.exhibition.is_users_voting_active:
							context['title'] = 'Доступ ограничен'
							context['message'] = f'Проект участвует в выставке "{project.exhibition.title}".'
							context['reason'] = 'active_exhibition'
							context['available_date'] = project.exhibition.date_end
			except (Portfolio.DoesNotExist, ValueError):
				pass

		return render(request, '404.html', context, status=404)

	except Exception as e:
		# Простой fallback
		logger.error(f"Ошибка в __404__: {e}")

		return HttpResponseNotFound("404 - Страница не найдена")
