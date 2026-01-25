import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View

from exhibition.models import Portfolio
from .models import Rating, Reviews
from .utils import is_jury_member


@method_decorator(csrf_exempt, name='dispatch')
class AddRating(View):
	"""Добавление рейтинга проекту"""

	def post(self, request):
		try:
			score = int(request.POST.get("star"))
			portfolio_id = int(request.POST.get("portfolio"))
			portfolio = Portfolio.objects.get(id=portfolio_id)

			# Проверяем базовые возможности оценки
			can_rate, message = Rating.can_user_rate(request.user, portfolio)
			if not can_rate:
				return JsonResponse({'status': 'error', 'message': message}, status=403)

			# Дополнительные проверки для выставки
			if portfolio.exhibition:
				# Проверяем сроки выставки
				from django.utils.timezone import now
				from datetime import timedelta

				rating_deadline = portfolio.exhibition.date_end - timedelta(days=1)
				is_jury = is_jury_member(request.user)

				# Если выставка активна, оценивать могут только жюри
				if now().date() <= rating_deadline and not is_jury:
					return JsonResponse({
						'status': 'error',
						'message': 'Во время выставки оценивать могут только члены жюри'
					}, status=403)

				# Если срок оценки истек, никто не может оценивать
				if now().date() > rating_deadline:
					return JsonResponse({
						'status': 'error',
						'message': 'Срок выставления оценок завершен'
					}, status=403)

			# Создаем или обновляем оценку
			is_jury = is_jury_member(request.user)
			rating, created = Rating.objects.update_or_create(
				user=request.user,
				portfolio=portfolio,
				defaults={
					'star': score,
					'is_jury_rating': is_jury,
					'ip': self.get_client_ip(request)
				}
			)

			return self._build_success_response(portfolio, score, is_jury, created)

		except (ValueError, TypeError) as e:
			return JsonResponse({
				'status': 'error',
				'message': f'Неверные данные: {str(e)}'
			}, status=400)
		except Portfolio.DoesNotExist:
			return JsonResponse({
				'status': 'error',
				'message': 'Работа не найдена'
			}, status=404)
		except Exception as e:
			return JsonResponse({
				'status': 'error',
				'message': f'Ошибка сервера: {str(e)}'
			}, status=500)

	def _build_success_response(self, portfolio, score, is_jury, created):
		"""Формирует успешный ответ"""
		from exhibition.logic import delete_cached_fragment
		delete_cached_fragment('portfolio', portfolio.id)
		delete_cached_fragment('project', portfolio.id)

		rating = Rating.objects.filter(portfolio=portfolio).first()
		if rating:
			rating.calculate()  # Обновляет атрибуты rating

		stats = portfolio.get_rating_stats()  # Получаем словарь

		response_data = {
			'score': score,
			'score_avg': stats['average'],
			'author': portfolio.owner.name,
			'is_jury': is_jury,
			'is_new': created,
			'jury_count': stats['jury_count'],
			'jury_avg': stats['jury_average']
		}

		return JsonResponse(response_data, safe=False)

	@staticmethod
	def get_client_ip(request):
		x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
		if x_forwarded_for:
			ip = x_forwarded_for.split(',')[0]
		else:
			ip = request.META.get('REMOTE_ADDR')
		return ip


@csrf_exempt
def add_review(request, pk):
	"""Комментарии"""

	try:
		if request.method == 'POST':
			parent = request.POST.get("parent")
			group = request.POST.get("group")
			message = request.POST.get("message")

			if not message:
				return JsonResponse({'error': 'Empty message'}, status=400)

			# Проверяем авторизацию
			if not request.user.is_authenticated:
				return JsonResponse({'error': 'Authentication required'}, status=403)

			# Создаем комментарий
			instance = Reviews.objects.create(
				user=request.user,
				portfolio_id=pk,
				parent_id=parent if parent else None,
				group_id=group if group else None,
				message=message,
			)

			# Подсчет количества ответов
			reply_count = 0
			if instance.parent_id:
				reply_count = Reviews.objects.filter(parent_id=instance.parent_id).count()

			# Формируем ответ
			new_comment = {
				'id': instance.pk,
				'parent': instance.parent_id,
				'group': instance.group_id,
				'author': instance.fullname,
				'message': instance.message,
				'posted_date': instance.posted_date.strftime('%d.%m.%Y'),
				'reply_count': reply_count,
			}

			return JsonResponse(new_comment, safe=False)

		else:
			return JsonResponse({'error': 'Method not allowed'}, status=405)

	except Exception as e:
		return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@csrf_exempt
@login_required
def edit_review(request, pk=None):

	if request.method == 'GET':
		try:
			instance = Reviews.objects.get(pk=pk, user=request.user)

			cleaned_message = re.sub(r"\s+", " ", instance.message.strip())
			return JsonResponse({
				'action': f'/review/edit/{pk}/',
				'form': f'''
					<div class="form-group">
						<textarea name="message" class="form-control" rows="5" placeholder="Введите ваш комментарий...">
							{cleaned_message}
						</textarea>
					</div>
					<input type="hidden" name="csrfmiddlewaretoken" value="{request.META['CSRF_COOKIE']}">
				''',
				'author_reply': instance.parent.fullname if instance.parent else ''
			})

		except Reviews.DoesNotExist:
			print(f"❌ Review not found: {pk}")
			return JsonResponse({
				'status': 'error',
				'message': 'Комментарий не существует!'
			}, status=404)

	elif request.method == 'POST':
		message = request.POST.get("message")

		try:
			instance = Reviews.objects.get(pk=pk, user=request.user)
			instance.message = re.sub(r"\s+", " ", message.strip())
			instance.save()

			return JsonResponse({
				'status': 'success',
				'id': instance.pk,
				'message': instance.message
			})

		except Reviews.DoesNotExist:
			return JsonResponse({
				'status': 'error',
				'message': 'Комментарий не существует!'
			}, status=404)

	return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required
def delete_review(request, pk=None):
	"""Удаление комментария - только POST запросы"""
	if request.method == 'POST':
		try:
			instance = Reviews.objects.get(pk=pk, user=request.user)
			instance.delete()

			return JsonResponse({
				'status': 'success',
				'message': 'Комментарий удален'
			})

		except Reviews.DoesNotExist:
			return JsonResponse({
				'status': 'error',
				'message': 'Комментарий не существует!'
			}, status=404)

	return JsonResponse({'error': 'Method not allowed'}, status=405)
