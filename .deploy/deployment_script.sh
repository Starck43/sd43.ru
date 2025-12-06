#!/bin/bash

set -e # Exit on error

# ======================
# 🔧 КОНФИГУРАЦИЯ
# ======================

# Обязательные параметры
PROJECT_NAME="${1:-app}"                     # Имя проекта (используется для именования сервисов)
PROJECT_DIR="${2:-/home/starck/domains/$PROJECT_NAME}"  # Путь к проекту
DJANGO_ADMIN_EMAIL="$3"                      # Email администратора
DJANGO_ADMIN_SUPERUSER="$4"                  # Имя пользователя администратора
DJANGO_ADMIN_PASSWORD="$5"                   # Пароль администратора

# Опциональные параметры (можно задать переменными окружения)
DOMAIN_NAME="${DOMAIN_NAME:-$PROJECT_NAME.ru}"           # Домен
SERVICE_USER="${SERVICE_USER:-starck}"                   # Пользователь для служб
SERVICE_GROUP="${SERVICE_GROUP:-starck}"                 # Группа для служб
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"                 # Версия Python
WSGI_MODULE="${WSGI_MODULE:-crm.wsgi:application}"       # WSGI модуль
DEPLOY_CONFIG_DIR="${DEPLOY_CONFIG_DIR:-.deploy}"        # Папка с конфигами деплоя

# Производные пути
VENV_DIR="$PROJECT_DIR/venv"
PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"
GUNICORN_SERVICE="$DEPLOY_CONFIG_DIR/gunicorn.service"
GUNICORN_SOCKET="$DEPLOY_CONFIG_DIR/gunicorn.socket"
NGINX_CONF="$DEPLOY_CONFIG_DIR/nginx.conf"

# ======================
# 🔧 ФУНКЦИИ
# ======================

print_header() {
    echo "========================================"
    echo "$1"
    echo "========================================"
}

print_step() {
    echo "▶ $1"
}

print_success() {
    echo "✅ $1"
}

print_warning() {
    echo "⚠️  $1"
}

print_error() {
    echo "❌ $1"
}

# Проверка и копирование файла если изменился
copy_if_changed() {
    local src="$1"
    local dst="$2"
    local description="${3:-$(basename "$dst")}"

    if [ ! -f "$src" ]; then
        print_warning "Source file not found: $src"
        return 1
    fi

    # Если файл назначения не существует ИЛИ исходный файл новее
    if [ ! -f "$dst" ] || [ "$src" -nt "$dst" ]; then
        print_step "Updating $description..."
        sudo cp "$src" "$dst"
        return 0  # Изменен
    else
        echo "   ✓ $description is up to date"
        return 1  # Не изменен
    fi
}

# Проверка существования .env файла
check_env_file() {
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        print_error "File .env does not exist in $PROJECT_DIR!"
        echo "Please create it before running the script."
        exit 1
    fi
    print_success ".env file found"
}

# Создание необходимых директорий с правами
create_project_directories() {
    # Конфигурация директорий: "путь:права:описание"
    local dirs_config=(
        "$PROJECT_DIR/media:775:Uploads and media files"
        "$PROJECT_DIR/static:755:Static assets"
        "$PROJECT_DIR/media/site:775:Admin site assets"
        "$PROJECT_DIR/logs:775:Application logs"
        "$PROJECT_DIR/temp:777:Temporary files"
    )

    print_step "Creating project directories..."

    for config in "${dirs_config[@]}"; do
        IFS=':' read -r dir permissions description <<< "$config"

        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            sudo chmod "$permissions" "$dir"
            echo "   Created: $dir ($description)"
        fi
    done

    # Единый владелец
    sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$PROJECT_DIR"
}

# Настройка systemd и nginx
setup_system_services() {
    local config_changed=false

    print_header "SYSTEM SERVICES SETUP"

    # 1. Gunicorn service
    if copy_if_changed "$GUNICORN_SERVICE" "/etc/systemd/system/$PROJECT_NAME.service" "systemd service"; then
        config_changed=true
    fi

    # 2. Gunicorn socket
    if copy_if_changed "$GUNICORN_SOCKET" "/etc/systemd/system/$PROJECT_NAME.socket" "systemd socket"; then
        config_changed=true
    fi

    # 3. Nginx config
    if copy_if_changed "$NGINX_CONF" "/etc/nginx/sites-available/$DOMAIN_NAME" "nginx config"; then
        config_changed=true
        sudo ln -sf "/etc/nginx/sites-available/$DOMAIN_NAME" "/etc/nginx/sites-enabled/"
    fi

    # Если конфиги менялись или сервисы не включены - перезагружаем
    if [ "$config_changed" = true ] || ! systemctl is-enabled "$PROJECT_NAME.socket" 2>/dev/null; then
        print_step "Reloading system services..."

        # Включаем сервисы если еще не включены
        if ! systemctl is-enabled "$PROJECT_NAME.socket" 2>/dev/null; then
            sudo systemctl enable "$PROJECT_NAME.socket"
            sudo systemctl enable "$PROJECT_NAME.service"
            print_success "Services enabled"
        fi

        # Перезагружаем systemd
        sudo systemctl daemon-reload
        print_success "Systemd daemon reloaded"

        # Проверяем и перезагружаем nginx
        if sudo nginx -t; then
            sudo systemctl reload nginx
            print_success "Nginx reloaded"
        else
            print_error "Nginx configuration test failed!"
            exit 1
        fi
    else
        print_success "All configs are up to date"
    fi
}

# Настройка Python окружения
setup_python_environment() {
    print_header "PYTHON ENVIRONMENT"

    if [ ! -d "$VENV_DIR" ]; then
        print_step "Creating virtual environment (Python $PYTHON_VERSION)..."
        python"$PYTHON_VERSION" -m venv "$VENV_DIR"

        print_step "Upgrading pip..."
        "$PIP" install --upgrade pip

        print_step "Installing dependencies..."
        "$PIP" install -r "$PROJECT_DIR/requirements.txt"

        print_success "Virtual environment created"
        return 0  # Первый запуск
    else
        print_step "Updating dependencies..."
        "$PIP" install pip --upgrade
        "$PIP" install -r "$PROJECT_DIR/requirements.txt" --upgrade
        print_success "Packages updated"
        return 1  # Обновление
    fi
}

# Настройка Django
setup_django() {
    print_header "DJANGO SETUP"

    local is_first_run=$1

    # Создаем директории если первый запуск
    if [ "$is_first_run" -eq 0 ]; then
        create_project_directories

        print_step "Running initial migrations..."
        "$PYTHON" "$PROJECT_DIR/manage.py" migrate auth --noinput
        "$PYTHON" "$PROJECT_DIR/manage.py" migrate --noinput

        print_step "Collecting static files..."
        "$PYTHON" "$PROJECT_DIR/manage.py" collectstatic --noinput

        # Создание суперпользователя
        if [ -n "$DJANGO_ADMIN_SUPERUSER" ] && [ -n "$DJANGO_ADMIN_EMAIL" ] && [ -n "$DJANGO_ADMIN_PASSWORD" ]; then
            print_step "Setting up superuser..."
            "$PYTHON" "$PROJECT_DIR/manage.py" shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if User.objects.filter(username='$DJANGO_ADMIN_SUPERUSER').exists():
    print('✅ Superuser $DJANGO_ADMIN_SUPERUSER already exists')
else:
    print('👤 Creating superuser $DJANGO_ADMIN_SUPERUSER...')
    User.objects.create_superuser('$DJANGO_ADMIN_SUPERUSER', '$DJANGO_ADMIN_EMAIL', '$DJANGO_ADMIN_PASSWORD')
    print('✅ Superuser created')
"
        else
            print_warning "Superuser credentials not provided, skipping..."
        fi
    fi

    # Всегда выполняем эти шаги
    print_step "Running migrations..."
    "$PYTHON" "$PROJECT_DIR/manage.py" makemigrations --noinput
    "$PYTHON" "$PROJECT_DIR/manage.py" migrate --noinput

    print_step "Collecting static files..."
    "$PYTHON" "$PROJECT_DIR/manage.py" collectstatic --noinput
}

# Запуск/перезапуск приложения
restart_application() {
    print_header "APPLICATION RESTART"

    print_step "Restarting $PROJECT_NAME.service..."
    sudo systemctl restart "$PROJECT_NAME.service"

    # Даем время на запуск
    sleep 2

    print_step "Checking service status..."
    if sudo systemctl is-active "$PROJECT_NAME.service" >/dev/null 2>&1; then
        print_success "Service $PROJECT_NAME.service is running"
        echo ""
        sudo systemctl status "$PROJECT_NAME.service" --no-pager | head -7
    else
        print_error "Service $PROJECT_NAME.service failed to start!"
        sudo systemctl status "$PROJECT_NAME.service" --no-pager
        exit 1
    fi
}

# ======================
# 🚀 ОСНОВНОЙ СКРИПТ
# ======================

print_header "DEPLOYMENT STARTED"
echo "Project:      $PROJECT_NAME"
echo "Directory:    $PROJECT_DIR"
echo "Domain:       $DOMAIN_NAME"
echo "Python:       $PYTHON_VERSION"
echo "User:         $SERVICE_USER"
echo ""

# 1. Проверка .env файла
check_env_file

# 2. Настройка systemd и nginx
setup_system_services

# 3. Настройка Python окружения
if setup_python_environment; then
    FIRST_RUN=0
else
    FIRST_RUN=1
fi

# 4. Настройка Django
setup_django "$FIRST_RUN"

# 5. Перезапуск приложения
restart_application

print_header "DEPLOYMENT COMPLETED"
echo "✅ Successfully deployed $PROJECT_NAME"
echo "🌐 Domain: $DOMAIN_NAME"
echo "📂 Project directory: $PROJECT_DIR"
echo "🐍 Python environment: $VENV_DIR"
echo ""
echo "Next steps:"
echo "1. Check the website: http://$DOMAIN_NAME"
echo "2. View logs: sudo journalctl -u $PROJECT_NAME.service -f"
echo "3. Monitor nginx: sudo tail -f /var/log/nginx/access.log"
