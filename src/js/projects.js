import {isInViewport} from './utils/viewport.js';
import {lazyloadInit} from './utils/lazyload.js';
import {createFormData} from "./utils/ajax.js";
import {rafThrottle} from "./utils/common.js";

document.addEventListener("DOMContentLoaded", function () {

    const contentBlock = document.querySelector('#projects');
    let preloader = document.querySelector('.preloader');

    if (!contentBlock || !preloader) return;

    let currentPage = 1;
    let hasNext = true;
    let loading = false;
    let canLoadNext = true; // Флаг для контроля задержки между загрузками

    // Используем rafThrottle для оптимизации
    const throttledCheck = rafThrottle(jsonRequest);

    function onScroll() {
        throttledCheck();
    }

    document.addEventListener('scroll', onScroll)

    /* ===============================
       HELPERS
    =============================== */

    function normalize(url, mediaUrl) {
        if (!url) return '';
        return url.startsWith('/media/')
            ? url
            : mediaUrl + url;
    }

    /* ===============================
       RENDER PROJECTS
    =============================== */

    function contentRender(data) {
        console.log(data.page)
        const projectsList = data.projects || [];

        let html = '';

        if (!Array.isArray(projectsList)) {
            console.error('Invalid projects payload', data);
            return;
        }

        // Если нет проектов, убираем preloader и останавливаем скроллинг
        if (projectsList.length === 0) {
            preloader.remove();
            document.removeEventListener('scroll', onScroll);
            return;
        }

        for (const project of projectsList) {
            const {
                id,
                title,
                owner__name: author,
                average,
                win_year,
                owner__slug,
                project_id,
                thumb_mini,
                thumb_xs,
                thumb_sm,
                thumb_xs_w = 320,
                thumb_sm_w = 576
            } = project;

            const score = average ? average.toFixed(1) : '';
            const url = `/projects/${owner__slug}/project-${project_id}/`;

            html += `
            <a id="project-${id}" class="grid-cell ratio centered" href="${url}" title="${title}">
                <figure>
                    <img class="project-cover lazyload"
                         src="${normalize(thumb_mini, data.media_url)}"
                         data-src="${normalize(thumb_sm, data.media_url)}"
                         data-srcset="
                            ${normalize(thumb_xs, data.media_url)} ${thumb_xs_w}w,
                            ${normalize(thumb_sm, data.media_url)} ${thumb_sm_w}w
                         "
                         data-sizes="auto"
                         loading="lazy"
                         alt="${title ? title + '. ' : ''}Автор проекта: ${author || ''}">
                    <figcaption class="d-flex-column">
                        ${title ? `<h3 class="project-title">${title}</h3>` : ''}
                        ${author ? `<div class="subtitle owner-name">${author}</div>` : ''}
                        <div class="extra d-flex justify-between">
                            ${win_year ? `<div class="portfolio-award d-flex">
                                            <svg class="award">
                                                <use xlink:href="#award-icon"></use>
                                            </svg>
                                        <span>${win_year}</span>
                                        </div>` : ''}
                            ${score ? `<div class="portfolio-rate d-flex">
                                            <span>${score}</span>
                                            <svg class="rate-star">
                                                <use xlink:href="#star-icon"></use>
                                            </svg>
                                        </div>` : ''}
                        </div>
                    </figcaption>
                </figure>
            </a>
        `;
        }

        if (html) {
            if (!preloader) {
                preloader = document.createElement('div');
                preloader.className = 'preloader';
                preloader.href = window.location.pathname;
                contentBlock.appendChild(preloader);
            }
            preloader.insertAdjacentHTML('beforebegin', html);
        }

        /* ===== STATE UPDATE ===== */

        currentPage = data.page;
        hasNext = data.has_next;
        loading = false;
        canLoadNext = true;

        if (!hasNext) {
            // Удаляем preloader только если больше нет страниц
            preloader.remove();
            // document.removeEventListener('scroll', onScroll);
        }

        lazyloadInit();
    }

    /* ===============================
       AJAX REQUEST
    =============================== */

    function jsonRequest() {
        if (!hasNext || loading || !preloader) return;
        if (!isInViewport(preloader, true)) return;

        loading = true;
        canLoadNext = false;
        preloader.classList.add('show');

        let params = 'page=' + (currentPage + 1);

        if (filterForm) {
            const filters = createFormData(filterForm);
            if (filters) {
                params += '&' + filters;
            }
        }

        window.ajaxSend(preloader.href, params, 'get', contentRender);
    }

    /* ===============================
       FILTERS
    =============================== */

    const filterForm = document.querySelector('form[name=projects-filter]');

    if (filterForm) {
        const filterCheckboxes = filterForm.querySelectorAll('input[type=checkbox]');
        const submitBtn = filterForm.querySelector('[type=submit]');

        function submitFilter(form) {
            currentPage = 1;
            hasNext = true;
            loading = false;

            // Удаляем все текущие проекты
            const projectElements = contentBlock.querySelectorAll('.grid-cell');
            projectElements.forEach(el => el.remove());

            // Восстанавливаем preloader
            preloader = document.querySelector('.preloader');
            if (!preloader) {
                preloader = document.createElement('div');
                preloader.id = 'preloader';
                preloader.className = 'preloader';
                preloader.href = form.action || window.location.pathname;
                contentBlock.appendChild(preloader);
            }

            preloader.classList.remove('hidden');
            preloader.classList.add('show');

            const params = createFormData(form);
            window.ajaxSend(
                form.action,
                'page=1&' + params,
                form.method,
                contentRender
            );
        }

        function clearCheckboxes() {
            filterCheckboxes.forEach(cb => cb.checked = false);
            checkActiveFilters(); // <-- ВАЖНО: обновляем состояние кнопки после очистки
        }

        function loadFiltersFromURL() {
            const urlParams = new URLSearchParams(window.location.search);
            const filterGroups = urlParams.getAll('filter-group');

            if (filterGroups.length) {
                filterCheckboxes.forEach(cb => {
                    if (filterGroups.includes(cb.value)) {
                        cb.checked = true;
                    }
                });
            }
            checkActiveFilters(); // обновляем состояние кнопки после загрузки
        }

        function checkActiveFilters() {
            const active = [...filterCheckboxes].some(cb => cb.checked);

            if (submitBtn) {
                submitBtn.disabled = !active;
            }

            contentBlock.classList.toggle('filtered', active);
        }

        // Обработчик изменения чекбоксов
        filterCheckboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                checkActiveFilters();

                // Задержка для предотвращения множественных запросов
                if (filterTimeout) clearTimeout(filterTimeout);
                filterTimeout = setTimeout(() => submitFilter(filterForm), 300);
            });
        });

        // Обработчик: в исходном коде очищает чекбоксы!
        filterForm.addEventListener('submit', function (e) {
            e.preventDefault();
            clearCheckboxes();
            submitFilter(this);
        });

        // если есть кнопка сброса вне формы
        const resetBtn = document.querySelector('[type="reset"], .reset-filters, .clear-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', function (e) {
                e.preventDefault();
                clearCheckboxes();
                submitFilter(filterForm);
            });
        }

        let filterTimeout = null;
        loadFiltersFromURL();
        checkActiveFilters();
    }

    /* ===============================
       AUTOLOAD IF SCREEN EMPTY
    =============================== */

    // Автозагрузка при инициализации
    setTimeout(() => {
        if (hasNext && preloader && isInViewport(preloader, true)) {
            jsonRequest();
        }
    }, 150);

});
