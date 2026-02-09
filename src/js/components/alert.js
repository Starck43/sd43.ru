/**
 * Alert component - notification messages
 */

export class Alert {
    constructor(element) {
        this.element = element;
        this.isClosing = false;
        this.ensureCloseButton();
        // Автоматически показываем alert при создании
        if (this.element.classList.contains('fade') && !this.element.classList.contains('show')) {
            this.show();
        }

        this.init();
    }

    init() {
        // Find close button (исправляем атрибут)
        const closeBtn = this.element.querySelector('[data-dismiss="alert"]');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.close();
            });
        }

        // Auto-close on ESC key
        this.handleEscape = (e) => {
            if (e.key === 'Escape') {
                this.close();
            }
        };
        window.addEventListener('keydown', this.handleEscape);
    }

    ensureCloseButton() {
        // Если кнопки закрытия нет - создаем ее
        if (!this.element.querySelector('[data-dismiss="alert"]')) {
            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'btn-close';
            closeBtn.setAttribute('data-dismiss', 'alert');
            closeBtn.setAttribute('aria-label', 'Close');
            closeBtn.innerHTML = `
                <svg class="close-icon icon">
                    <use xlink:href="#close-icon"></use>
                </svg>
            `;

            // Вставляем в начало алерта
            this.element.insertBefore(closeBtn, this.element.firstChild);
        }
    }

    show() {
        setTimeout(() => {
            this.element.classList.add('show');
        }, 10);
    }

    close() {
        if (this.isClosing) return;

        this.isClosing = true;

        const closeEvent = new CustomEvent('alert:close', {bubbles: true});
        this.element.dispatchEvent(closeEvent);

        // Убираем show для запуска анимации исчезновения
        this.element.classList.remove('show');

        setTimeout(() => {
            const closedEvent = new CustomEvent('alert:closed', {bubbles: true});
            this.element.dispatchEvent(closedEvent);

            this.element.remove();
            window.removeEventListener('keydown', this.handleEscape);
        }, 300);
    }

    static getInstance(element) {
        return element?._alertInstance || null;
    }

    static create(element) {
        if (!element) return null;

        let instance = Alert.getInstance(element);
        if (!instance) {
            instance = new Alert(element);
            element._alertInstance = instance;
        }
        return instance;
    }
}

/**
 * Отображает сообщение-уведомление
 * @param {string} html - HTML-содержимое для отображения в уведомлении
 * @param {Object} options - Настройки уведомления
 * @param {string} [options.type='info'] - Тип уведомления (success, warning, error, info)
 * @param {number} [options.duration=5000] - Время автоматического закрытия в мс (0 для ручного закрытия)
 * @param {string} [options.position='top-right'] - Позиция на экране (top-right, top-center, bottom-right, bottom-center)
 * @returns {Alert|null} - Экземпляр Alert или null в случае ошибки
 */
export function alertHandler(content, options = {}) {
    const config = {
        type: 'info',
        duration: 3000,
        position: 'top-right',
        ...options
    };

    let htmlContent;
    if (Array.isArray(content)) {
        // Если передан массив - создаем список
        htmlContent = '<ul>';
        content.forEach(item => {
            htmlContent += `<li>${item}</li>`;
        });
        htmlContent += '</ul>';
    } else if (typeof content === 'string' && content.includes('<ul')) {
        // Если это уже готовый HTML - используем как есть
        htmlContent = content;
    } else {
        // Обычный текст или HTML
        htmlContent = content;
    }

    // Создаем alert элемент
    const alertElement = document.createElement('div');
    alertElement.className = `alert alert-${config.type} fade ${config.position} box-shadow`;
    alertElement.setAttribute('role', 'alert');

    alertElement.innerHTML = `
        <button type="button" class="btn-close bn-md" data-dismiss="alert" aria-label="Закрыть">
            <svg class="close-icon icon">
                <use xlink:href="#close-icon"></use>
            </svg>
        </button>
        <div class="alert-body">${htmlContent}</div>
    `;

    // Добавляем сразу в body
    document.body.appendChild(alertElement);

    // Создаем экземпляр Alert
    const alertInstance = Alert.create(alertElement);

    // Авто-закрытие
    if (config.duration > 0) {
        setTimeout(() => {
            alertInstance.close();
        }, config.duration);
    }

    return alertInstance;
}

/**
 * Менеджер уведомлений - методы для быстрого создания уведомлений разных типов
 * @namespace AlertManager
 * @property {function} success - Создает успешное уведомление
 * @property {function} warning - Создает предупреждение
 * @property {function} error - Создает ошибку
 * @property {function} info - Создает информационное уведомление
 */
export const AlertManager = {
    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    success: (html, duration = 5000, position = 'top-center') =>
        alertHandler(html, {type: 'success', duration, position}),

    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    warning: (html, duration = 5000, position = 'top-center') =>
        alertHandler(html, {type: 'warning', duration, position}),

    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    error: (html, duration = 0, position = 'top-center') =>
        alertHandler(html, {type: 'error', duration, position}),

    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    info: (html, duration = 5000, position = 'top-center') =>
        alertHandler(html, {type: 'info', duration, position}),

    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    danger: (html, duration = 0, position = 'top-center') =>
        alertHandler(html, {type: 'danger', duration, position}),

    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    primary: (html, duration = 5000, position = 'top-center') =>
        alertHandler(html, {type: 'primary', duration, position}),

    /**
     * @param {string} html - HTML-содержимое
     * @param {number} duration - Время автоматического закрытия
     * @param {string} position - Позиция на экране
     */
    light: (html, duration = 3000, position = 'bottom-center') =>
        alertHandler(html, {type: 'light', duration, position})
};

