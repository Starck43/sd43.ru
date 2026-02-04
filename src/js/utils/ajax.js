/**
 * Отправка AJAX запроса
 * @param {string} url - URL для запроса
 * @param {string} params - параметры запроса
 * @param {string} method - метод запроса
 * @param {Function} renderFunc - функция для рендеринга результата
 * @param {boolean} showAlert - флаг для отображения ошибок через модальное окно
 */
export function ajaxSend(
    url, params = '',
    method = 'post',
    renderFunc = defaultRender,
    showAlert = false
) {
    // Формируем URL для GET запросов
    const requestUrl = method.toLowerCase() === 'get' ? `${url}?${params}` : url;

    // Конфигурация запроса
    const requestConfig = {
        method: method,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    };

    // Для POST запросов добавляем тело
    if (method.toLowerCase() === 'post') {
        requestConfig.headers['Content-Type'] = 'application/x-www-form-urlencoded';
        requestConfig.body = params;
    }

    // Отправляем запрос
    fetch(requestUrl, requestConfig)
        .then(response => {
            if (!response.ok) {
                throw new Error(`❌ HTTP error!\nstatus: ${response.status}`);
            }
            return response.json();
        })
        .then(json => {
            if (typeof renderFunc === 'function') {
                renderFunc(json);
            } else {
                console.warn('❌ Render function not provided', json);
                defaultRender(json);
            }
        })
        .catch((error) => {
            console.error('❌ AJAX Error:', error);

            if (showAlert) {
                // Используем глобальную систему уведомлений
                const errorMessage = getErrorMessage(error);
                showGlobalError(errorMessage);
            }
        });
}


/**
 * Получение понятного сообщения об ошибке
 */
function getErrorMessage(error) {
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
        return 'Ошибка сети: невозможно подключиться к серверу';
    } else if (error.message.includes('HTTP error! status: 403')) {
        return 'У вас нет прав для этого действия';
    } else if (error.message.includes('HTTP error! status: 404')) {
        return 'Страница не найдена';
    } else if (error.message.includes('HTTP error')) {
        return `Ошибка сервера: ${error.status}`;
    } else if (error.message.includes('Доступ запрещен')) {
        return 'У вас нет прав для этого действия';
    } else {
        return error.message || 'Неизвестная ошибка';
    }
}

/**
 * Показ ошибки через глобальную систему уведомлений
 */
function showGlobalError(message) {
    if (window.Alert) {
        window.Alert.error(`<h3>Ошибка!</h3><p>${message}</p>`);
    } else {
        // Fallback: простой alert если система уведомлений не загружена
        alert(`Ошибка сервера: ${message}`);
    }
}

/**
 * Функция по умолчанию для рендеринга
 */
function defaultRender(json) {
    // Если в ответе есть сообщение, показываем его
    if (json.message && window.Alert) {
        const messageType = json.status === 'error' ? 'error' : 'success';
        window.Alert[messageType]?.(json.message);
    }
}

/**
 * Утилита для создания параметров из FormData
 */
export function createFormData(formElement) {
    return new URLSearchParams(new FormData(formElement)).toString();
}

/**
 * Утилита для создания параметров из объекта
 */
export function createParamsFromObject(obj) {
    return new URLSearchParams(obj).toString();
}

