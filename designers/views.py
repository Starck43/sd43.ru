from itertools import chain

from django.db.models import Q, OuterRef, Subquery, Prefetch, CharField, Case, When
from django.db.models.expressions import F
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView

from exhibition.logic import send_email
from exhibition.mixins import MetaSeoMixin
from exhibition.models import Categories, Nominations, Winners, Portfolio, Image
from .forms import FeedbackForm
from .mixins import DesignerAccessMixin
from .models import Designer, Achievement


class MainPage(DesignerAccessMixin, MetaSeoMixin, DetailView):
	model = Designer
	template_name = 'designers/main_page.html'
	form_class = FeedbackForm

	def get_portfolio_with_cover(self, portfolio_queryset):
		"""Общий метод для аннотации портфолио с обложкой"""
		return portfolio_queryset.filter(status=True).annotate(
			exh_year=F('exhibition__slug'),
			win_year=Subquery(
				Winners.objects.filter(portfolio_id=OuterRef('pk')).values('exhibition__slug')[:1]
			),
			project_cover=Case(
				When(
					Q(cover__exact='') | Q(cover__isnull=True),
					then=Subquery(Image.objects.filter(portfolio_id=OuterRef('pk')).values('file')[:1])
				),
				default='cover',
				output_field=CharField()
			)
		)

	def get_context_data(self, **kwargs):
		designer = self.object

		# Упрощаем: пробуем выставочные, если нет - дополнительное
		portfolio = self.get_portfolio_with_cover(designer.exh_portfolio).order_by('-exh_year')

		if not portfolio:
			portfolio = self.get_portfolio_with_cover(designer.add_portfolio).order_by('order')

		victories = Nominations.objects.filter(
			nomination_for_winner__exhibitor=designer.owner
		).prefetch_related('nomination_for_winner').annotate(
			exh_year=F('nomination_for_winner__exhibition__slug')
		).values('title', 'slug', 'exh_year').order_by('-exh_year')

		context = super().get_context_data(**kwargs)
		context.update({
			'html_classes': ['designer-page'],
			'about': designer.about or designer.owner.description,
			'portfolio_list': portfolio,
			'exh_victories_list': victories,
			'competitions': designer.achievements.filter(~Q(group=2)),
			'publications': designer.achievements.filter(group=2),
			'form': self.form_class(),
		})
		return context


class PortfolioPage(DesignerAccessMixin, MetaSeoMixin, DetailView):
	model = Designer
	template_name = 'designers/portfolio_page.html'
	form_class = FeedbackForm

	def get_portfolio_with_details(self, designer):
		"""Получить все портфолио"""
		exh_ids = designer.exh_portfolio.values_list('pk', flat=True)
		add_ids = designer.add_portfolio.values_list('pk', flat=True)

		return Portfolio.objects.filter(
			pk__in=list(chain(exh_ids, add_ids)),
			status=True
		).prefetch_related(
			Prefetch('nominations', queryset=Nominations.objects.order_by('slug'), to_attr='nominations_list'),
			Prefetch('categories', queryset=Categories.objects.order_by('slug'), to_attr='categories_list')
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
			),
		).order_by('order')

	def get_filter_attributes(self, designer):
		"""Получить категории для фильтрации"""
		exh_category = designer.exh_portfolio.prefetch_related('nominations__category').annotate(
			category_slug=F('nominations__category__slug'),
			category_name=F('nominations__category__title')
		).values_list('category_slug', 'category_name')

		add_category = designer.add_portfolio.prefetch_related('categories').annotate(
			category_slug=F('categories__slug'),
			category_name=F('categories__title')
		).values_list('category_slug', 'category_name')

		return list(filter(lambda x: x[0] is not None, set(tuple(exh_category) + tuple(add_category))))

	def get_context_data(self, **kwargs):
		designer = self.object
		context = super().get_context_data(**kwargs)

		context.update({
			'html_classes': ['designer-page', 'portfolio'],
			'portfolio_list': self.get_portfolio_with_details(designer),
			'filter_attributes': self.get_filter_attributes(designer),
			'page_url': self.request.build_absolute_uri(),
			'parent_link': designer.get_absolute_url(),
			'page_path': designer.get_portfolio_url(),
			'form': self.form_class(),
		})
		return context


class PortfolioDetailPage(DesignerAccessMixin, MetaSeoMixin, DetailView):
	model = Designer
	template_name = 'designers/portfolio_detail.html'
	form_class = FeedbackForm

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		designer = self.object
		project_id = self.kwargs['project_id']

		portfolio = Portfolio.objects.filter(
			owner=designer.owner,
			project_id=project_id,
			status=True
		).first()

		if not portfolio:
			raise Http404('Проект не найден')

		context['html_classes'] = ['designer-page', 'project']
		context['project'] = portfolio
		context['page_url'] = self.request.build_absolute_uri()
		context['parent_link'] = designer.get_portfolio_url()
		context['page_path'] = designer.get_project_url(project_id)
		context['cache_timeout'] = 86400
		context['form'] = FeedbackForm()
		return context


@csrf_exempt
def send_message(request, slug):
	""" Отправка сообщения с формы обратной связи """
	try:
		designer = Designer.objects.get_by_slug(slug=slug)
		if designer.owner.email:
			recipients = [designer.owner.email]
		else:
			recipients = [designer.owner.user.email]

		if request.is_ajax():
			data = {
				'subdomain': designer.slug,
				'name': request.GET.get("name", None),
				'email': request.GET.get("from_email", None),
				'message': request.GET.get("message", None)
			}

			if email_confirmation(data, recipients):
				return JsonResponse({'status': 'success'}, safe=False)
			# return HttpResponse(status=201)
			else:
				return JsonResponse({'status': 'error'}, safe=False)

	# return HttpResponse(status=400)

	# form = FeedbackForm(request.POST)
	# if form.is_valid():
	# 	data = {
	# 		'subdomain' :designer.slug,
	# 		'name'		:form.cleaned_data['name'],
	# 		'email'		:form.cleaned_data['from_email'],
	# 		'message'	:form.cleaned_data['message']
	# 	}
	# 	print(data, recipients)
	# 	if email_confirmation(data, recipients):
	# 		return redirect('/success/')

	except Designer.DoesNotExist:
		redirect('/')


def email_confirmation(data, recipients):
	""" Отправка уведомления дизайнеру на почту """
	if data['message'] and data['email']:
		template = render_to_string('designers/confirm_email.html', {
			'subdomain': data['subdomain'],
			'name': data['name'],
			'email': data['email'],
			'message': data['message'],
		})
		# отправка письма на почту дизайнера
		return send_email('Сообщение с сайта', template, recipients)
