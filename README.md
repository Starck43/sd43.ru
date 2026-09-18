# Выставка Сфера Дизайна (sd43.ru)

**Выставка Сфера Дизайна** — веб-платформа для демонстрации портфолио дизайнеров-участников выставок компании «Арт-Сервис»: управление выставками, номинациями и портфолио, рейтинги и отзывы, блог, баннеры партнёров и персональные сайты дизайнеров на поддоменах `<slug>.sd43.ru`.

## Технологический стек

### Backend
- **Django 6.x** — `requirements.txt` перечисляет состав зависимостей без пинов версий; фактические версии — в окружении `venv/` (`pip list`)
- **PostgreSQL** (прод) / **SQLite** (дефолт дева) — подключение через `dj-database-url` (`DATABASE_URL`)
- **Redis** — кэш (`django-redis`, отдельный `THUMBNAIL_REDIS_URL` для sorl-thumbnail)
- **Gunicorn** + **nginx** — прод-окружение (см. `.deploy/`)
- **CKEditor 5** (`django-ckeditor-5`) + **Jazzmin** — админ-интерфейс
- **django-allauth** — вход через VK, Одноклассники, Google

### Frontend
- **esbuild** — сборка JS и CSS через `build.mjs` (Gulp не используется)
- **SASS/SCSS**, **PostCSS** (autoprefixer, import)
- **Swiper**, **jQuery**, **lazysizes**, **isotope-layout**, **imagesloaded**, **highlight.js**

### Прочее
- **sorl-thumbnail** — миниатюры
- **django-watson** — полнотекстовый поиск
- **Яндекс Метрика** — аналитика (`templates/metrika.html`)
- `sitemap.xml` — `django.contrib.sitemaps` (основной сайт + отдельные карты для поддоменов дизайнеров)

## Структура проекта

```
.
├── crm/            # конфигурация проекта: settings, urls, middleware, wsgi
├── exhibition/     # ядро: выставки, участники, номинации, портфолио, победители
├── designers/      # персональные сайты дизайнеров (<slug>.sd43.ru)
├── rating/         # рейтинги и отзывы
├── blog/           # статьи
├── ads/            # баннеры партнёров
├── templates/      # Django-шаблоны (base.html, exhibition/, designers/, ...)
├── src/            # исходники фронтенда: js/, sass/, fonts/
├── static/         # собранные ассеты (результат build.mjs) и legacy-файлы
├── media/          # загруженные пользователями файлы (не в git)
├── build.mjs       # esbuild-сборка ассетов
├── .deploy/        # nginx.conf, systemd-юнит, deployment_script.sh
└── .github/        # CI/CD: деплой по push в master
```

> **Важно:** миграции не хранятся в git — они генерируются командой `makemigrations`
> прямо на сервере при деплое (см. `.deploy/deployment_script.sh`).

## Переменные окружения

Настройки читаются из `.env` (дев) / `prod.env` (прод). Ключи:
`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`,
`THUMBNAIL_REDIS_URL`, `EMAIL_URL`, `EMAIL_RECIPIENTS`,
`YANDEX_CAPTCHA_CLIENT_KEY`, `YANDEX_CAPTCHA_SERVER_KEY`,
`PORTFOLIO_COUNT_PER_PAGE`, `ARTICLES_COUNT_PER_PAGE`.

Значения по умолчанию и семантика — в `crm/settings.py`. Файла `.env.example`
в репозитории нет; секреты не коммитятся.

## Установка и запуск (локально)

Требования: Python 3.12+, Node LTS (в CI — 22), Redis. PostgreSQL опционален — без
`DATABASE_URL` проект работает на SQLite. `requirements.txt` задаёт состав
зависимостей без версий; фактические версии — в окружении `venv/` в корне проекта.

```bash
git clone https://github.com/Starck43/sd43.ru.git sd43
cd sd43
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
npm install
# создайте .env: минимум SECRET_KEY, DEBUG=true, ALLOWED_HOSTS=localhost,127.0.0.1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver          # http://localhost:8000/admin/
npm run watch:dev                   # второй терминал: пересборка фронтенда
```

Перед изменением моделей полезно проверить расхождение локального состояния со
серверным: `python manage.py makemigrations --check --dry-run` (см. «Деплой»).

## Сборка фронтенда

Команды, watch-режимы и подводные камни — в [BUILD.md](BUILD.md).

## Поддомены дизайнеров

Один Django-проект обслуживает и основной сайт, и персональные сайты дизайнеров
`designer.sd43.ru` — роутинг по `Host` в `designers/middleware.py`
(`SubdomainMiddleware`). Для локальной проверки поддомена добавьте запись в
`/etc/hosts` (например `atrium.localhost`) и включите этот хост в `ALLOWED_HOSTS`.

## Деплой

Push в `master` → GitHub Actions (`.github/workflows/main.yml`) → rsync на сервер
(список исключений — сам `.gitignore`) → на сервере выполняются `makemigrations`,
`migrate`, `collectstatic` → перезапуск gunicorn (systemd). Статику и медиа
раздаёт nginx, он же роутит поддомены дизайнеров.

Следствия:
- миграции в git не попадают — генерируются на сервере;
- `.gitignore` используется и как rsync-exclude: новая ignore-строка меняет состав
  деплоя, а `!`-негации rsync не поддерживаются.

## Администрирование

`/admin/` (Jazzmin): выставки, участники, номинации, портфолио, победители,
баннеры, статьи, отзывы.

## Версия и лицензия

- Версия продукта — `VERSION` в `crm/project.py` (пакетная — в `package.json`)
- Лицензия — ISC (см. `package.json`)

## Контакты

Разработчик: S.Shabalin · Компания: Арт-Сервис

© 2008–2026 Все права защищены
