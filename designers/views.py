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
	""" Главная страница дизайнера """
	model = Designer
	template_name = 'designers/main_page.html'
	form_class = FeedbackForm

	def get_context_data(self, **kwargs):
		designer = self.object

		portfolio = self.object.exh_portfolio.filter(status=True).annotate(
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

		if not portfolio:
			portfolio = self.object.add_portfolio.filter(status=True).annotate(
				project_cover=Case(
					When(
						Q(cover__exact='') | Q(cover__isnull=True),
						then=Subquery(Image.objects.filter(portfolio_id=OuterRef('pk')).values('file')[:1])
					),
					default='cover',
					output_field=CharField()
				)
			).order_by('order')

		victories = Nominations.objects.prefetch_related('nomination_for_winner').filter(
			nomination_for_winner__exhibitor=designer.owner).annotate(
			exh_year=F('nomination_for_winner__exhibition__slug')
		).values('title', 'slug', 'exh_year').order_by('-exh_year')

		competitions = Achievement.objects.filter(Q(Q(designer=designer) & ~Q(group=2)))
		publications = Achievement.objects.filter(designer=designer, group=2)

		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['designer-page']
		context['about'] = self.object.about if self.object.about else self.object.owner.description
		context['portfolio_list'] = portfolio
		context['exh_victories_list'] = victories
		context['competitions'] = competitions
		context['publications'] = publications
		context['form'] = FeedbackForm()

		return context


class PortfolioPage(DesignerAccessMixin, MetaSeoMixin, DetailView):
	""" Страница с портфолио """
	model = Designer
	template_name = 'designers/portfolio_page.html'
	form_class = FeedbackForm

	def get_context_data(self, **kwargs):
		designer = self.object

		exh_ids = designer.exh_portfolio.values_list('pk', flat=True)
		add_ids = designer.add_portfolio.values_list('pk', flat=True)
		owner_portfolio_ids = list(chain(exh_ids, add_ids))

		all_portfolio = Portfolio.objects.filter(pk__in=owner_portfolio_ids, status=True).prefetch_related(
			Prefetch('nominations', queryset=Nominations.objects.order_by('slug'), to_attr='nominations_list')
		).prefetch_related(
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

		exh_category = designer.exh_portfolio.prefetch_related('nominations__category').annotate(
			category_slug=F('nominations__category__slug'),
			category_name=F('nominations__category__title')
		).values_list('category_slug', 'category_name')
		add_category = designer.add_portfolio.prefetch_related('categories').annotate(
			category_slug=F('categories__slug'),
			category_name=F('categories__title')
		).values_list('category_slug', 'category_name')

		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['designer-page', 'portfolio']
		context['portfolio_list'] = all_portfolio
		context['filter_attributes'] = list(
			filter(lambda x: x[0] is not None, set(tuple(exh_category) + tuple(add_category)))
		)
		context['page_url'] = self.request.build_absolute_uri()
		context['parent_link'] = reverse('designers:designer-page-url', kwargs={'slug': designer.slug})
		context['page_path'] = reverse('designers:portfolio-page-url', kwargs={'slug': designer.slug})
		context['form'] = FeedbackForm()
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
		context['page_path'] = reverse(
			'designers:portfolio-detail-page-url',
			kwargs={'slug': designer.slug, 'project_id': project_id}
		)
		context['parent_link'] = reverse(
			'designers:portfolio-page-url',
			kwargs={'slug': designer.slug}
		)
		context['cache_timeout'] = 86400
		context['form'] = FeedbackForm()
		return context


@csrf_exempt
def send_message(request, slug):
	""" Отправка сообщения с формы обратной связи """
	try:
		designer = Designer.objects.get(slug=slug)
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
