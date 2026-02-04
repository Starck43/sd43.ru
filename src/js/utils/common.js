export function rafThrottle(func) {
    let ticking = false;
    return function (...args) {
        if (!ticking) {
            requestAnimationFrame(() => {
                func.apply(this, args);
                ticking = false;
            });
            ticking = true;
        }
    };
}

export function normalizeImageUrl(url, mediaUrl = '', placeholder = '') {
    if (!url) return placeholder;
    return url.startsWith('/media/')
        ? url
        : mediaUrl + url;
}

/**
 * Проверка, является ли устройство мобильным
 * @returns {boolean}
 */
export function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}


// Функция автоматического изменения высоты textarea
export function autoResizeTextarea(textarea) {
    // Сбрасываем высоту, чтобы получить правильный scrollHeight
    textarea.style.height = 'auto';

    // Устанавливаем высоту based on scrollHeight
    const newHeight = Math.min(textarea.scrollHeight, 300); // Максимум 300px
    textarea.style.height = newHeight + 'px';

    // Показываем/скрываем скролл
    textarea.style.overflowY = textarea.scrollHeight > 300 ? 'auto' : 'hidden';
}

// Инициализация авто-размера для всех textarea на странице
export function initAutoResizeTextareas() {
    document.querySelectorAll('textarea').forEach(textarea => {
        autoResizeTextarea(textarea);
        textarea.addEventListener('input', () => autoResizeTextarea(textarea));
    });
}
