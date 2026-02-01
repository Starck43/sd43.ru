# exhibition/exports.py
from io import BytesIO
from urllib.parse import quote

import xlsxwriter
from django.contrib import admin
from django.db.models import Sum
from django.http import HttpResponse
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

		# Получаем параметр количества проектов для отображения
		projects_per_nom = request.GET.get('limit', self.DEFAULT_PROJECTS_PER_NOMINATION)
		try:
			projects_per_nom = int(projects_per_nom)
		except:
			projects_per_nom = self.DEFAULT_PROJECTS_PER_NOMINATION

		if request.method == 'POST':
			filename = request.POST.get('filename', '').strip()
			if not filename:
				filename = f"оценки_жюри_{exhibition.slug}"

			# Получаем ВСЕ данные для Excel
			report_data = self._get_report_data(exhibition, 1000)
			return self._generate_excel_report(exhibition, filename, report_data)

		# GET запрос - отображаем страницу
		report_data = self._get_report_data(exhibition, projects_per_nom)

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
	def _get_report_data(exhibition, projects_per_nomination):
		"""Получаем все данные для отчета"""
		# Жюри, участвующие в этой выставке
		jury_list = exhibition.jury.all()

		# Собираем общую статистику
		report_data = {
			'jury_list': jury_list,
			'nominations': [],
			'jury_stats': {},
			'not_voted_jury': {},  # Изменяем структуру
			'total_stats': {
				'total_jury': jury_list.count(),
				'total_nominations': exhibition.nominations.count(),
				'total_projects': 0,
				'total_ratings': 0,
			}
		}

		# Статистика по каждому жюри
		for jury in jury_list:
			# Количество оценок этого жюри для проектов выставки
			ratings_count = Rating.objects.filter(
				user=jury.user,
				is_jury_rating=True,
				portfolio__exhibition=exhibition
			).count()

			# Общая сумма оценок этого жюри
			ratings_sum = Rating.objects.filter(
				user=jury.user,
				is_jury_rating=True,
				portfolio__exhibition=exhibition
			).aggregate(Sum('star'))['star__sum'] or 0

			report_data['jury_stats'][jury.id] = {
				'name': jury.name or jury.user_name,
				'ratings_count': ratings_count,
				'ratings_sum': ratings_sum,
			}
			report_data['total_stats']['total_ratings'] += ratings_count

		# Инициализируем структуру для не проголосовавших жюри
		for jury in jury_list:
			report_data['not_voted_jury'][jury.id] = {
				'jury': jury,
				'nominations': [],
				'total_missing': 0
			}

		# Обрабатываем каждую номинацию
		for nomination in exhibition.nominations.all():
			# Проекты в этой номинации, участвующие в выставке
			# Важно: один и тот же проект может быть в нескольких номинациях
			portfolios = Portfolio.objects.filter(
				exhibition=exhibition,
				nominations=nomination
			).prefetch_related(
				'ratings__user',
				'ratings',
				'owner'
			).distinct()

			# Собираем данные по проектам
			projects_data = []
			voted_projects_count = 0
			nomination_total_score = 0

			# Агрегация по жюри для этой номинации
			nomination_jury_totals = {jury.id: 0 for jury in jury_list}
			nomination_jury_counts = {jury.id: 0 for jury in jury_list}

			for portfolio in portfolios:
				project = {
					'portfolio': portfolio,
					'jury_scores': {},
					'total_score': 0,
					'has_ratings': False
				}

				# Собираем оценки жюри этой выставки ТОЛЬКО для этой номинации
				for jury in jury_list:
					# Ищем оценку конкретно для этого проекта от этого жюри
					rating = portfolio.ratings.filter(
						user=jury.user,
						is_jury_rating=True
					).first()

					score = rating.star if rating else None
					project['jury_scores'][jury.id] = score

					if score:
						voted_projects_count += 1
						project['total_score'] += score
						project['has_ratings'] = True
						nomination_jury_totals[jury.id] += score
						nomination_jury_counts[jury.id] += 1

				# Обновляем статистику по жюри для не проголосовавших
				for jury in jury_list:
					if jury.id not in project['jury_scores'] or project['jury_scores'][jury.id] is None:
						# Жюри не оценил этот проект
						if not any(
								n['nomination'] == nomination
								for n in report_data['not_voted_jury'][jury.id]['nominations']
						):
							# Добавляем номинацию если её ещё нет
							report_data['not_voted_jury'][jury.id]['nominations'].append({
								'nomination': nomination,
								'voted': nomination_jury_counts[jury.id],
								'total': portfolios.count(),
								'missing': portfolios.count() - nomination_jury_counts[jury.id]
							})
							report_data['not_voted_jury'][jury.id]['total_missing'] += (
									portfolios.count() - nomination_jury_counts[jury.id]
							)

				projects_data.append(project)
				nomination_total_score += project['total_score']

			# Сортируем по убыванию общей суммы
			projects_data.sort(key=lambda x: x['total_score'], reverse=True)

			# Разделяем на топ и остальные проекты
			top_projects = projects_data[:projects_per_nomination]
			other_projects = projects_data[projects_per_nomination:]

			# Определяем победителей (может быть несколько при равенстве баллов)
			winners = []
			if projects_data and len(jury_list) * portfolios.count() == voted_projects_count:
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

		# Жюри, которые не проголосовали полностью: корректировка
		report_data['not_voted_jury'] = {
			jury_id: data for jury_id, data in report_data['not_voted_jury'].items()
			if data['total_missing'] > 0
		}

		return report_data

	def _generate_excel_report(self, exhibition, custom_filename=None, report_data=None):
		"""Генерация Excel отчета"""
		if report_data is None:
			report_data = self._get_report_data(exhibition, 1000)  # Все проекты

		try:
			output = BytesIO()
			workbook = xlsxwriter.Workbook(output)

			# Форматы
			header_format = workbook.add_format({
				'bold': True,
				'align': 'center',
				'bg_color': '#D9E1F2',
				'border': 1
			})

			title_format = workbook.add_format({
				'bold': True,
				'font_size': 16,
				'align': 'center'
			})

			nomination_format = workbook.add_format({
				'bold': True,
				'bg_color': '#F2F2F2',
				'border': 1
			})

			total_format = workbook.add_format({
				'bold': True,
				'bg_color': '#FCE4D6',
				'border': 1
			})

			winner_format = workbook.add_format({
				'bold': True,
				'font_color': '#C65911',
				'border': 1
			})

			# Лист 1: Оценки по номинациям
			worksheet = workbook.add_worksheet('Оценки жюри')

			row = 0
			col = 0

			# Заголовок
			worksheet.merge_range(row, col, row, len(report_data['jury_list']) + 1,
			                      f'Протокол оценок жюри: {exhibition.title}',
			                      title_format)
			row += 2

			# Данные по номинациям
			for nomination in report_data['nominations']:
				# Заголовок номинации
				worksheet.merge_range(row, col, row, len(report_data['jury_list']) + 1,
				                      nomination['title'],
				                      nomination_format)
				row += 1

				# Заголовки колонок
				worksheet.write(row, col, '№', header_format)
				worksheet.write(row, col + 1, 'Проект', header_format)
				col_idx = 2

				for jury in report_data['jury_list']:
					# Сокращаем имя жюри для заголовка
					jury_name = jury.name if jury.name else jury.user_name
					if len(jury_name) > 15:
						jury_name = jury_name[:12] + '...'
					worksheet.write(row, col_idx, jury_name, header_format)
					col_idx += 1

				worksheet.write(row, col_idx, 'Сумма баллов', header_format)
				row += 1

				# Данные проектов
				project_num = 1
				all_projects = nomination['top_projects'] + nomination['other_projects']

				for project in all_projects:
					# Проверяем, является ли проект победителем
					is_winner = any(
						w['portfolio'].id == project['portfolio'].id
						for w in nomination['winners']
					)

					current_format = winner_format if is_winner else None

					worksheet.write(row, col, project_num, current_format)
					worksheet.write(row, col + 1, str(project['portfolio']), current_format)

					col_idx = 2
					for jury in report_data['jury_list']:
						score = project['jury_scores'].get(jury.id)
						worksheet.write(row, col_idx, score if score else '', current_format)
						col_idx += 1

					worksheet.write(row, col_idx, project['total_score'], total_format)

					row += 1
					project_num += 1

				# Пустая строка между номинациями
				row += 2
				col_idx = 0

			# Лист 2: Победители
			winners_worksheet = workbook.add_worksheet('Победители')

			row = 0
			col = 0

			# Заголовок
			winners_worksheet.merge_range(row, col, row, 3,
			                              f'Победители выставки: {exhibition.title}',
			                              title_format)
			row += 2

			# Заголовки таблицы
			winners_worksheet.write(row, col, 'Номинация', header_format)
			winners_worksheet.write(row, col + 1, 'Проект', header_format)
			winners_worksheet.write(row, col + 2, 'Участник', header_format)
			winners_worksheet.write(row, col + 3, 'Сумма баллов', header_format)
			row += 1

			# Данные победителей
			for nomination in report_data['nominations']:
				if nomination['winners']:
					for winner in nomination['winners']:
						winners_worksheet.write(row, col, nomination['title'])
						winners_worksheet.write(row, col + 1, winner['portfolio'].title)
						winners_worksheet.write(row, col + 2, winner['portfolio'].owner.name)
						winners_worksheet.write(row, col + 3, winner['score'])
						row += 1
				else:
					winners_worksheet.write(row, col, nomination['title'])
					winners_worksheet.write(row, col + 1, 'Победитель не определен')
					winners_worksheet.write(row, col + 2, '-')
					winners_worksheet.write(row, col + 3, '-')
					row += 1

			# Автоматическая ширина колонок
			worksheet.autofit()
			winners_worksheet.autofit()

			workbook.close()
			output.seek(0)

			response = HttpResponse(
				output.getvalue(),
				content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
			)

			# Формируем имя файла
			if custom_filename and custom_filename.strip():
				filename = f"{custom_filename.strip()}.xlsx"
			else:
				filename = f"sd43_vote_{exhibition.slug}.xlsx"

			# Кодируем для безопасной работы с русскими символами
			encoded_filename = quote(filename)
			response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"

			return response

		except Exception as e:
			print(f"ERROR in _generate_excel_report: {str(e)}")
			import traceback
			traceback.print_exc()
			# Возвращаем ошибку пользователю
			from django.http import HttpResponseBadRequest
			return HttpResponseBadRequest(f"Ошибка при формировании файла: {str(e)}")
