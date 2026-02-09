# exhibition/management/commands/confirm_existing_emails.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from django.db import IntegrityError, transaction


class Command(BaseCommand):
	help = 'Подтверждает email всех существующих пользователей'

	def add_arguments(self, parser):
		parser.add_argument(
			'--dry-run',
			action='store_true',
			help='Показать что будет сделано без изменений в БД',
		)
		parser.add_argument(
			'--fix-duplicates',
			action='store_true',
			help='Показать пользователей с одинаковыми email',
		)

	def handle(self, *args, **options):
		User = get_user_model()
		dry_run = options['dry_run']
		fix_duplicates = options['fix_duplicates']

		total = User.objects.count()
		self.stdout.write(f"Найдено {total} пользователей")

		if dry_run:
			self.stdout.write("🔶 РЕЖИМ ПРОСМОТРА (без изменений в БД)")

		# 1. Сначала найдем дубликаты email среди пользователей
		self.stdout.write("\n🔍 Поиск пользователей с одинаковыми email...")

		from django.db.models import Count
		duplicate_emails = User.objects.values('email').annotate(
			count=Count('id')
		).filter(count__gt=1, email__isnull=False).exclude(email='')

		if duplicate_emails:
			self.stdout.write(self.style.WARNING(f"⚠️  Найдено {len(duplicate_emails)} дубликатов email:"))
			for item in duplicate_emails:
				users = User.objects.filter(email=item['email'])
				self.stdout.write(f"   📧 {item['email']} ({item['count']} пользователей):")
				for user in users:
					self.stdout.write(f"      👤 {user.username} (id={user.id}, дата: {user.date_joined.date()})")

			if fix_duplicates:
				self.stdout.write("\n🔧 Исправление дубликатов...")
				self.fix_duplicate_emails(duplicate_emails, dry_run)
		else:
			self.stdout.write("✅ Дубликатов email не найдено")

		# 2. Подтверждаем email
		self.stdout.write("\n📝 Подтверждение email пользователей...")

		confirmed_count = 0
		created_count = 0
		error_count = 0

		for user in User.objects.all().order_by('date_joined'):
			if not user.email:
				self.stdout.write(f"  ⚠️  Пропуск: {user.username} (нет email)")
				continue

			try:
				# Проверяем существует ли уже EmailAddress с этим email
				existing_email = EmailAddress.objects.filter(email=user.email).exclude(user=user).first()

				if existing_email:
					self.stdout.write(self.style.WARNING(
						f"  ⚠️  Конфликт: email {user.email} уже используется пользователем "
						f"{existing_email.user.username} (id={existing_email.user.id})"
					))

					# Предлагаем альтернативный email для текущего пользователя
					alt_email = f"{user.username}@sd43.ru"
					self.stdout.write(f"      Предлагаю использовать: {alt_email}")

					if not dry_run:
						# Обновляем email пользователя
						user.email = alt_email
						user.save()

						# Создаем EmailAddress с альтернативным email
						EmailAddress.objects.create(
							user=user,
							email=alt_email,
							verified=True,
							primary=True
						)
						self.stdout.write(f"      ✅ Обновлен на: {alt_email}")

					created_count += 1
					continue

				# Обычный случай - создаем или обновляем
				with transaction.atomic():
					obj, created = EmailAddress.objects.update_or_create(
						user=user,
						email=user.email,
						defaults={
							'verified': True,
							'primary': True
						}
					)

				if created:
					self.stdout.write(f"  📝 Создан: {user.email} для {user.username}")
					created_count += 1
				elif not obj.verified:
					self.stdout.write(f"  ✅ Подтвержден: {user.email} для {user.username}")
					confirmed_count += 1
				else:
					self.stdout.write(f"  ℹ️ Уже подтвержден: {user.email}")

			except IntegrityError as e:
				self.stdout.write(self.style.ERROR(f"  ❌ Ошибка для {user.username}: {str(e)}"))
				error_count += 1
				# Пропускаем этого пользователя
				continue

		# Итог
		self.stdout.write("\n" + "=" * 50)
		self.stdout.write("ИТОГ:")
		self.stdout.write(f"  Всего пользователей: {total}")
		self.stdout.write(f"  Подтверждено: {confirmed_count}")
		self.stdout.write(f"  Создано: {created_count}")
		self.stdout.write(f"  Ошибок: {error_count}")

		if duplicate_emails:
			self.stdout.write(self.style.WARNING(
				f"  ⚠️  Дубликатов email: {len(duplicate_emails)}"
			))
			self.stdout.write("     Запустите с --fix-duplicates для исправления")

		if dry_run:
			self.stdout.write(self.style.WARNING("⚠️  РЕЖИМ ПРОСМОТРА - изменения НЕ сохранены"))
			self.stdout.write("   Для реального выполнения уберите --dry-run")
		elif error_count == 0:
			self.stdout.write(self.style.SUCCESS("✅ Все email обработаны успешно!"))
		else:
			self.stdout.write(self.style.ERROR(f"⚠️  Было {error_count} ошибок"))

	def fix_duplicate_emails(self, duplicate_emails, dry_run=False):
		"""Исправление дубликатов email"""
		User = get_user_model()

		for item in duplicate_emails:
			email = item['email']
			users = User.objects.filter(email=email).order_by('date_joined')

			# Оставляем email у самого старого пользователя
			primary_user = users.first()
			self.stdout.write(f"\n📧 Исправление для email: {email}")
			self.stdout.write(f"   ✅ Оставляем у: {primary_user.username} (самый старый)")

			# У остальных меняем email
			for user in users[1:]:
				new_email = f"{user.username}@{user.date_joined.strftime('%Y%m%d')}.sd43.ru"
				self.stdout.write(f"   🔄 Меняем у {user.username}: {email} → {new_email}")

				if not dry_run:
					user.email = new_email
					user.save()

					# Создаем EmailAddress для нового email
					EmailAddress.objects.create(
						user=user,
						email=new_email,
						verified=True,
						primary=True
					)

