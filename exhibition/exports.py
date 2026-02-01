# exhibition/exports.py
from django.contrib import admin
from django.shortcuts import render, get_object_or_404
from django.urls import path, reverse

from exhibition.models import Exhibitions, Portfolio
from rating.models import Rating


class ExportExhibitionAdmin(admin.ModelAdmin):
	DEFAULT_PROJECTS_PER_NOMINATION = 3

	def get_urls(self):
		urls = super().get_urls()
		info = self.model._meta.app_label, self.model._meta.model_name

		custom_urls = [
			path(
				'<path:object_id>/export-jury-ratings/',
				self.admin_site.admin_view(self.export_jury_ratings),
				name='%s_%s_export_jury_ratings' % info,
			),
		]
		return custom_urls + urls

	def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
		extra_context = extra_context or {}
		if object_id:
			extra_context['show_export_button'] = True
			info = self.model._meta.app_label, self.model._meta.model_name
			extra_context['export_url'] = reverse(
				'admin:%s_%s_export_jury_ratings' % info,
				args=[object_id]
			)
		return super().changeform_view(request, object_id, form_url, extra_context)

	def export_jury_ratings(self, request, object_id):
		"""Страница экспорта оценок жюри"""
		exhibition = get_object_or_404(Exhibitions, pk=object_id)

		# Получаем параметр количества проектов
		projects_per_nom = request.GET.get('limit', self.DEFAULT_PROJECTS_PER_NOMINATION)
		try:
			projects_per_nom = int(projects_per_nom)
			# Ограничиваем для отображения страницы
			projects_per_nom = min(projects_per_nom, 10)  # Максимум 10 для отображения
		except:
			projects_per_nom = min(self.DEFAULT_PROJECTS_PER_NOMINATION, 10)

		# Если это POST запрос для экспорта
		if request.method == 'POST':
			filename = request.POST.get('filename', '').strip()
			if not filename:
				filename = f"оценки_жюри_{exhibition.slug}"

			# Для экспорта используем легковесную функцию
			return self._lightweight_export(exhibition, filename)

		# GET запрос - отображаем страницу с ограниченными данными
		# for_export=False - получаем только данные для отображения
		report_data = self._get_report_data(exhibition, projects_per_nom, for_export=False)

		context = {
			**self.admin_site.each_context(request),
			'title': f'Протокол оценок жюри: {exhibition.title}',
			'exhibition': exhibition,
			'report_data': report_data,
			'projects_per_nomination': projects_per_nom,
			'opts': self.model._meta,
		}

		return render(request, 'admin/exhibition/jury_ratings_export.html', context)

	@staticmethod
	def _get_report_data(exhibition, projects_per_nomination, for_export=False):
		"""Получаем все данные для отчета"""

		# Жюри, участвующие в этой выставке
		jury_list = exhibition.jury.all().only('id', 'name', 'user_id')

		# Для экспорта загружаем только необходимые поля
		if for_export:
			jury_list = list(jury_list.values('id', 'name', 'user_id'))

		report_data = {
			'jury_list': jury_list,
			'nominations': [],
			'jury_stats': {},
			'not_voted_jury': {},
			'total_stats': {
				'total_jury': len(jury_list),
				'total_nominations': exhibition.nominations.count(),
				'total_projects': 0,
				'total_ratings': 0,
			}
		}

		# Инициализируем структуру для не проголосовавших жюри
		for jury in jury_list:
			jury_id = jury['id'] if for_export else jury.id
			report_data['not_voted_jury'][jury_id] = {
				'jury': jury,
				'nominations': [],
				'total_missing': 0
			}

		# Статистика по каждому жюри - оптимизированный запрос
		from django.db.models import Count, Sum
		for jury in jury_list:
			if for_export:
				jury_id = jury['id']
				user_id = jury['user_id']
				jury_name = jury['name']
			else:
				jury_id = jury.id
				user_id = jury.user_id
				jury_name = jury.name

			# Используем агрегацию, вместо загрузки всех объектов
			ratings_info = Rating.objects.filter(
				user_id=user_id,
				is_jury_rating=True,
				portfolio__exhibition=exhibition
			).aggregate(
				count=Count('id'),
				sum=Sum('star')
			)

			report_data['jury_stats'][jury_id] = {
				'name': jury_name,
				'ratings_count': ratings_info['count'] or 0,
				'ratings_sum': ratings_info['sum'] or 0,
			}
			report_data['total_stats']['total_ratings'] += ratings_info['count'] or 0

		# Обрабатываем каждую номинацию
		nominations = exhibition.nominations.all().only('id', 'title')

		for nomination in nominations:
			# Оптимизированный запрос для портфолио
			portfolios = Portfolio.objects.filter(
				exhibition=exhibition,
				nominations=nomination
			).only('id', 'title', 'owner_id', 'project_id')

			# Оптимизация: получаем только ID портфолио
			portfolio_ids = list(portfolios.values_list('id', flat=True))

			if not portfolio_ids:
				# Пропускаем пустые номинации
				continue

			# Получаем оценки для этих портфолио одним запросом
			ratings_data = Rating.objects.filter(
				portfolio_id__in=portfolio_ids,
				is_jury_rating=True
			).values('portfolio_id', 'user_id').annotate(
				star_sum=Sum('star')
			)

			# Создаем словарь для быстрого доступа
			ratings_dict = {}
			for rd in ratings_data:
				key = (rd['portfolio_id'], rd['user_id'])
				ratings_dict[key] = rd['star_sum']

			# Собираем данные по проектам
			projects_data = []
			nomination_total_score = 0
			nomination_jury_totals = {}
			nomination_jury_counts = {}

			# Инициализируем словари для статистики по жюри
			for jury in jury_list:
				jury_id = jury['id'] if for_export else jury.id
				nomination_jury_totals[jury_id] = 0
				nomination_jury_counts[jury_id] = 0

			for portfolio in portfolios:
				portfolio_id = portfolio.id
				project = {
					'portfolio': portfolio,
					'jury_scores': {},
					'total_score': 0,
					'has_ratings': False
				}

				# Для экспорта загружаем дополнительные данные
				if for_export:
					portfolio_full = Portfolio.objects.filter(id=portfolio_id).select_related('owner').first()
					if portfolio_full:
						project['portfolio'] = portfolio_full

				# Собираем оценки жюри
				for jury in jury_list:
					if for_export:
						jury_id = jury['id']
						user_id = jury['user_id']
					else:
						jury_id = jury.id
						user_id = jury.user_id

					key = (portfolio_id, user_id)
					score = ratings_dict.get(key)

					project['jury_scores'][jury_id] = score

					if score:
						project['total_score'] += score
						project['has_ratings'] = True
						nomination_jury_totals[jury_id] += score
						nomination_jury_counts[jury_id] += 1

				projects_data.append(project)
				nomination_total_score += project['total_score']

			# Сортируем по убыванию общей суммы
			projects_data.sort(key=lambda x: x['total_score'], reverse=True)

			# Разделяем на топ и остальные проекты
			top_projects = projects_data[:projects_per_nomination]
			other_projects = projects_data[projects_per_nomination:]

			# Определяем победителей (может быть несколько при равенстве баллов)
			winners = []
			if projects_data:
				# Исправляем подсчет voted_projects_count
				voted_projects_count = 0
				for project in projects_data:
					# Считаем сколько жюри оценили этот проект
					rated_jury_count = sum(1 for score in project['jury_scores'].values() if score is not None)
					if rated_jury_count == len(jury_list):  # Все жюри оценили проект
						voted_projects_count += 1

				total_possible_votes = len(jury_list) * len(projects_data)
				actual_votes = sum(nomination_jury_counts.values())  # Общее количество выставленных оценок

				# Условие для определения победителей: все жюри оценили все проекты
				if actual_votes == total_possible_votes:
					# Все жюри оценили все проекты в номинации
					max_score = projects_data[0]['total_score']

					# Находим все проекты с максимальным баллом
					top_scorers = [p for p in projects_data if p['total_score'] == max_score]

					for project in top_scorers:
						winners.append({
							'portfolio': project['portfolio'],
							'score': project['total_score'],
							'medal': 'gold',
							'position': 1
						})

			# Обновляем статистику по жюри для не проголосовавших
			for jury in jury_list:
				if for_export:
					jury_id = jury['id']
				else:
					jury_id = jury.id

				expected_count = len(projects_data)
				actual_count = nomination_jury_counts.get(jury_id, 0)

				if actual_count < expected_count:
					missing_nomination = None
					for nom in report_data['not_voted_jury'][jury_id]['nominations']:
						if nom['nomination'].id == nomination.id:
							missing_nomination = nom
							break

					if not missing_nomination:
						report_data['not_voted_jury'][jury_id]['nominations'].append({
							'nomination': nomination,
							'voted': actual_count,
							'total': expected_count,
							'missing': expected_count - actual_count
						})
						report_data['not_voted_jury'][jury_id]['total_missing'] += (expected_count - actual_count)

			nomination_data = {
				'title': nomination.title,
				'id': nomination.id,
				'all_projects': len(projects_data),
				'top_projects': top_projects,
				'other_projects': other_projects,
				'winners': winners,
				'total_score': nomination_total_score,
				'jury_totals': nomination_jury_totals,
				'jury_counts': nomination_jury_counts
			}

			report_data['nominations'].append(nomination_data)
			report_data['total_stats']['total_projects'] += len(projects_data)

		# Удаляем жюри, которые проголосовали за все проекты
		report_data['not_voted_jury'] = {
			jury_id: data for jury_id, data in report_data['not_voted_jury'].items()
			if data['total_missing'] > 0
		}

		return report_data

	def _lightweight_export(self, exhibition, filename):
		"""Оптимизированный экспорт для больших данных"""

		from django.db import connection
		import xlsxwriter
		from io import BytesIO
		from django.http import HttpResponse, HttpResponseServerError

		try:
			# Используем существующий метод для получения данных
			# for_export=True - получаем данные в легковесном формате
			report_data = self._get_report_data(exhibition, 200, for_export=True)

			# Проверяем есть ли данные
			if not report_data['nominations']:
				return HttpResponseServerError("Нет данных для экспорта")

			# Генерируем Excel
			output = BytesIO()
			workbook = xlsxwriter.Workbook(output, {'in_memory': True})

			# Форматы
			header_format = workbook.add_format({'bold': True, 'align': 'center'})

			# Лист 1: Оценки
			worksheet = workbook.add_worksheet('Оценки')

			row = 0
			worksheet.write(row, 0, f'Протокол оценок жюри: {exhibition.title}')
			row += 2

			for nomination in report_data['nominations']:
				worksheet.write(row, 0, nomination['title'])
				row += 1

				# Заголовки
				worksheet.write(row, 0, 'Проект', header_format)
				col = 1

				for jury in report_data['jury_list']:
					if isinstance(jury, dict):
						jury_name = jury['name']
					else:
						jury_name = jury.name
					worksheet.write(row, col, jury_name[:20] if jury_name else '', header_format)
					col += 1

				worksheet.write(row, col, 'Сумма', header_format)
				row += 1

				# Данные проектов
				all_projects = nomination['top_projects'] + nomination['other_projects']
				for project in all_projects:
					portfolio_obj = project['portfolio']
					if hasattr(portfolio_obj, 'title'):
						project_name = portfolio_obj.title
					else:
						project_name = str(portfolio_obj)

					worksheet.write(row, 0, project_name)

					col = 1
					for jury in report_data['jury_list']:
						if isinstance(jury, dict):
							jury_id = jury['id']
						else:
							jury_id = jury.id

						score = project['jury_scores'].get(jury_id)
						worksheet.write(row, col, score if score else '')
						col += 1

					worksheet.write(row, col, project['total_score'])
					row += 1

				row += 1  # Пустая строка

			# Лист 2: Победители
			winners_worksheet = workbook.add_worksheet('Победители')
			row = 0
			winners_worksheet.write(row, 0, 'Номинация', header_format)
			winners_worksheet.write(row, 1, 'Проект', header_format)
			winners_worksheet.write(row, 2, 'Автор', header_format)
			winners_worksheet.write(row, 3, 'Баллы', header_format)
			row += 1

			for nomination in report_data['nominations']:
				for winner in nomination['winners']:
					winners_worksheet.write(row, 0, nomination['title'])
					winners_worksheet.write(row, 1, winner['portfolio'].title)
					winners_worksheet.write(row, 2, winner['portfolio'].owner.name)
					winners_worksheet.write(row, 3, winner['score'])
					row += 1

			workbook.close()
			output.seek(0)

			response = HttpResponse(
				output.getvalue(),
				content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
			)

			if not filename.lower().endswith('.xlsx'):
				filename = f"{filename}.xlsx"

			#response['Content-Disposition'] = f'attachment; filename="{filename}"'
			from urllib import parse
			encoded_filename = parse.quote(filename)

			response['Content-Disposition'] = (
				f'attachment; filename="{parse.quote(filename)}"; '
				f'filename*=UTF-8\'\'{encoded_filename}'
			)

			# Дополнительные заголовки для лучшей совместимости
			response['Content-Length'] = len(output.getvalue())
			response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
			response['Pragma'] = 'no-cache'
			response['Expires'] = '0'

			return response

		except Exception as e:
			import traceback
			print(f"ERROR in lightweight export: {str(e)}")
			traceback.print_exc()
			return HttpResponseServerError(f"Ошибка экспорта: {str(e)}")


	def _generate_excel_report(self, exhibition, custom_filename=None, report_data=None):
		"""Генерация Excel отчета с оптимизацией памяти"""
		try:
			import xlsxwriter
			from io import BytesIO

			output = BytesIO()
			workbook = xlsxwriter.Workbook(output, {'in_memory': True})

			# Упрощенные форматы для экономии памяти
			header_format = workbook.add_format({'bold': True, 'align': 'center'})

			# Лист 1: Оценки по номинациям
			worksheet = workbook.add_worksheet('Оценки жюри')

			# Пишем данные порционно
			row = 0
			worksheet.write(row, 0, f'Протокол оценок жюри: {exhibition.title}')
			row += 2

			for nomination in report_data['nominations']:
				worksheet.write(row, 0, nomination['title'])
				row += 1

				# Заголовки
				worksheet.write(row, 0, 'Проект', header_format)
				col = 1
				for jury in report_data['jury_list']:
					jury_name = jury.name if hasattr(jury, 'name') else jury['name']
					worksheet.write(row, col, jury_name[:20], header_format)
					col += 1
				worksheet.write(row, col, 'Сумма', header_format)
				row += 1

				# Данные проектов - пишем порционно
				all_projects = nomination['top_projects'] + nomination['other_projects']
				for project in all_projects:
					worksheet.write(row, 0, str(project['portfolio']))

					col = 1
					for jury in report_data['jury_list']:
						jury_id = jury.id if hasattr(jury, 'id') else jury['id']
						score = project['jury_scores'].get(jury_id)
						worksheet.write(row, col, score if score else '')
						col += 1

					worksheet.write(row, col, project['total_score'])
					row += 1

				row += 1  # Пустая строка

			workbook.close()
			output.seek(0)

			# Формируем ответ
			filename = f"{custom_filename.strip()}.xlsx" if custom_filename else f"оценки_жюри_{exhibition.slug}.xlsx"

			from django.http import HttpResponse
			response = HttpResponse(
				output.getvalue(),
				content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
			)
			response['Content-Disposition'] = f'attachment; filename="{filename}"'

			return response

		except Exception as e:
			print(f"ERROR in _generate_excel_report: {str(e)}")
			import traceback
			traceback.print_exc()
			raise
