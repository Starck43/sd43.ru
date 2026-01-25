import {Alert} from "./alert.js";
import {Offcanvas} from "./offcanvas.js";
import {Collapse} from "./collapse.js";
import {smoothScroll} from '../utils/viewport.js';
import {isMobile, rafThrottle} from "../utils/common.js";

/**
 * Инициализация основных компонентов интерфейса
 */
export function initComponents() {
    let scrollDown = document.querySelector('.scroll-down');
    const scrollUp = document.querySelector('#back2top');
    const searchContainer = document.querySelector('#searchContainer');

    // Обработчик скролла страницы
    const handleScroll = rafThrottle(() => {
        const scrollY = window.scrollY;
        const viewportHeight = window.innerHeight;

        // Кнопка "Вниз" - удаляем при скролле
        if (scrollDown && scrollY >= viewportHeight) {
            scrollDown.remove();
            scrollDown = null;
        }

        // Кнопка "Вверх" - показ/скрытие
        if (scrollUp) {
            const shouldShow = scrollY > viewportHeight;
            scrollUp.classList.toggle('disable', !shouldShow);
            scrollUp.style.transform = shouldShow ? 'translateY(0)' : 'translateY(4vh)';
        }

        // Поиск - закрываем при скролле
        if (searchContainer?.classList.contains('active')) {
            searchContainer.classList.remove('active');
        }
    });

    document.addEventListener('scroll', handleScroll, {passive: true});

    // Удаление класса loading с элементов
    const loadingElements = document.querySelectorAll('.loading');
    loadingElements.forEach((item) => {
        item.classList.remove('loading');
        item.classList.add('loaded');
    });

    // Обработчик кнопки "Вверх"
    scrollUp?.addEventListener('click', (e) => {
        e.preventDefault();
        smoothScroll(0, 0);
    });

    // Обработчик кнопки "Вниз"
    scrollDown?.addEventListener('click', (e) => {
        e.preventDefault();
        smoothScroll(0, -window.innerHeight);
    });

    initOffcanvases();      // Выдвижные панели
    initSearch();           // Поиск
    initAlerts();           // Уведомления
    initCollapse();         // Сворачиваемые блоки
    initCollapsedBlocks();  // Свернутые блоки
}

/**
 * Инициализация всех navbar и sidebar offcanvas элементов
 */
function initOffcanvases() {
    const triggers = document.querySelectorAll('[data-toggle="offcanvas"]');
    triggers.forEach(trigger => {
        const targetSelector = trigger.getAttribute('data-target');
        if (!targetSelector) return;

        const target = document.querySelector(targetSelector);
        if (!target) return;

        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            new Offcanvas(target).toggle();
        });
    });
}

/**
 * Инициализация уведомлений
 */
export function initAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        Alert.create(alert);
    });
}

/**
 * Инициализация функционала поиска
 */
function initSearch() {
    const searchContainer = document.querySelector('#searchContainer');
    if (!searchContainer) return;

    const searchInput = searchContainer.querySelector('[type=search]');
    const clearInput = searchContainer.querySelector('.clear-input');
    const searchLinks = document.querySelectorAll('.nav-search-link');

    // Обработчик нажатия на кнопку поиска
    searchLinks.forEach((item) => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            searchContainer.classList.toggle('active');

            if (searchContainer.classList.contains('active')) {
                if (searchInput.value) {
                    clearInput?.classList.add('show');
                }
                searchInput.focus();
            } else {
                searchInput.blur();
            }
        });
    });

    // Обработчик очистки содержимого поля для текста
    clearInput?.addEventListener('click', () => {
        searchInput.value = '';
        searchInput.focus();
        clearInput.classList.remove('show');
    });

    // Обработчик ввода текста в поле поиска
    searchInput?.addEventListener('input', (e) => {
        if (e.target.value.length > 0) {
            clearInput?.classList.add('show');
        } else {
            clearInput?.classList.remove('show');
        }
    });

    // Закрытие окна поиска по клавише Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && searchContainer.classList.contains('active')) {
            searchContainer.classList.remove('active');
        }
    });
}

/**
 * Инициализация функциональности сворачивания для всех элементов с data-toggle="collapse"
 */
function initCollapse() {
    const toggles = document.querySelectorAll('[data-toggle="collapse"]');

    toggles.forEach(toggle => {
        // Если уже инициализирован - пропускаем
        if (toggle.dataset.collapseInitialized) return;
        toggle.dataset.collapseInitialized = 'true';

        const targetSelector = toggle.getAttribute('href') || toggle.getAttribute('data-target');
        if (!targetSelector) return;

        const target = document.querySelector(targetSelector);
        if (!target) return;

        toggle.addEventListener('click', (e) => {
            if (window.innerWidth >= 992 || !isMobile()) return;

            e.preventDefault();
            e.stopPropagation();

            new Collapse(target).toggle();

            requestAnimationFrame(() => {
                const isNowExpanded = target.classList.contains('show');
                toggle.setAttribute('aria-expanded', isNowExpanded.toString());
            });
        });
    });
}

/**
 * Инициализация разворачиваемых блоков
 */
function initCollapsedBlocks() {
    const collapsedBlocks = document.querySelectorAll('.collapsed');

    collapsedBlocks.forEach((item) => {
        item.addEventListener('click', (e) => {
            if (e.target.tagName === 'A' || e.target.closest('a')) {
                return;
            }

            if (e.currentTarget.classList.contains('collapsed')) {
                e.currentTarget.classList.remove('collapsed');
                e.currentTarget.classList.add('expanded');
            } else if (e.currentTarget.classList.contains('expanded')) {
                e.currentTarget.classList.remove('expanded');
                e.currentTarget.classList.add('collapsed');
            }
        }, {passive: true});
    });
}
