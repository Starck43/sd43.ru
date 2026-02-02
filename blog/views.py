from django.conf import settings
from django.db.models import Count
from django.http import JsonResponse
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from exhibition.mixins import BannersMixin, MetaSeoMixin
from .models import Category, Article


class ArticleList(MetaSeoMixin, BannersMixin, ListView):
	model = Article
	template_name = 'blog/article_list.html'

	PAGE_SIZE = getattr(settings, 'ARTICLES_COUNT_PER_PAGE', 10)  # Количество выводимых записей на странице

	def get_queryset(self):
		# self.page - текущая страница для получения диапазона выборки записей,  (см. функцию get ниже )
		self.page = int(self.page) if self.page else 1

		start_page = (self.page - 1) * self.PAGE_SIZE  # начало диапазона
		end_page = self.page * self.PAGE_SIZE  # конец диапазона

		# Если выбраны опции фильтра, то найдем все номинации в текущей категории "self.slug"
		# +1 сделано для выявления наличия следующей страницы
		if self.filter_cat and self.filter_cat != 'all':
			# query = Q(category_id=int(self.filter_cat))
			posts = self.model.objects.filter(category_id=int(self.filter_cat))[start_page:end_page + 1]
		else:
			posts = self.model.objects.all()[start_page:end_page + 1]

		self.is_next_page = False if len(posts) <= self.PAGE_SIZE else True
		return posts  # [:self.PAGE_SIZE]

	def get(self, request, *args, **kwargs):
		self.page = self.request.GET.get('page', None)  # Параметр GET запроса ?page текущей страницы
		# Выбранные опции checkbox в GET запросе (?nominations=[])
		self.filter_cat = self.request.GET.get("article-category", None)

		if self.filter_cat or self.page:
			queryset = self.get_queryset()
			article_list = list(queryset.values())
			if self.is_next_page:
				article_list.pop()

			for i, q in enumerate(article_list):
				person = queryset[i].person()
				if person:
					q.update({'person': person.name})
					q.update({'person_url': person.get_absolute_url()})

			json_data = {
				'current_page': int(self.page or 1),
				'next_page': self.is_next_page,
				'articles': list(article_list),
				# 'media_url': settings.MEDIA_URL,
			}
			return JsonResponse(json_data, safe=False)
		else:
			# выполняется при загрузке первой страницы
			return super().get(request, **kwargs)

	def get_context_data(self, **kwargs):
		attrs = (
			Category.objects.prefetch_related('article_set')
			.annotate(count=Count('article'))
			.filter(count__gt=0).values('id', 'name', 'count')
		)

		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['articles', ]
		context['page_title'] = self.model._meta.verbose_name_plural
		context['article_list'] = self.object_list[:self.PAGE_SIZE]
		context['filter_attributes'] = attrs
		context['cache_timeout'] = 86400
		return context


class ArticleDetail(MetaSeoMixin, BannersMixin, DetailView):
	model = Article

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['html_classes'] = ['article']
		context['parent_link'] = '/articles/'
		context['cache_timeout'] = 86400
		return context
