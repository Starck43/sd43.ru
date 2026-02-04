import {isInViewport} from './utils/viewport.js';
import {lazyloadInit} from './utils/lazyload.js';
import {createFormData} from "./utils/ajax.js";
import {normalizeImageUrl, rafThrottle} from "./utils/common.js";


document.addEventListener("DOMContentLoaded", function () {

    let preloader = document.querySelector('#preloader');
    let currentPage = 1, nextPage = true;
    let preloaderVisible = false;

    const throttledJsonRequest = rafThrottle(jsonRequest);


    function contentRender(data) {
        const projectsList = data['projects_list'];
        const defaultPlaceholder = data['default_placeholder'];
        const mediaUrl = data['media_url']
        const getImageUrl = (url) => normalizeImageUrl(url, mediaUrl, defaultPlaceholder);

        const html = projectsList
            .map(project => createProjectHTML(project, getImageUrl))
            .join('');

        if (html) {
            nextPage = data['next_page'];
            currentPage = data['current_page'];

            if (currentPage === 1) {
                const clone = preloader.cloneNode(true);
                contentBlock.innerHTML = html;
                contentBlock.append(clone);
                preloader = clone;
                if (nextPage) {
                    preloader.classList.remove('hidden');
                    preloader.classList.add('show');
                }

            } else {
                // Вставим контент перед прелоадером
                preloader.insertAdjacentHTML('beforebegin', html);
            }
            throttledJsonRequest(); // сразу подгрузим следующий контент, если прелоадер остался в зоне видимости
            lazyloadInit();

        } else nextPage = false;


        if (nextPage === false) {
            document.removeEventListener('scroll', throttledJsonRequest);
            preloader.classList.remove('show');
            window.setTimeout(() => {
                preloader.classList.add('hidden');
            }, 200);
        }
    }

    function createProjectHTML(project, imageFunc) {
        const {
            id, title, owner__name: author, average, win_year,
            owner__slug, project_id, thumb_mini, thumb_xs, thumb_sm,
            thumb_xs_w = 320, thumb_sm_w = 576
        } = project;

        const width = (w) => w ? `${w}w` : '';

        return `
            <a id="project-${id}" class="grid-cell ratio centered" href="/projects/${owner__slug}/project-${project_id}/" title="${title || ''}">
                <figure>
                    <img class="project-cover lazyload"
                         src="${imageFunc(thumb_mini)}"
                         data-src="${imageFunc(thumb_sm)}"
                         data-srcset="${imageFunc(thumb_xs)} ${width(thumb_xs_w)}, ${imageFunc(thumb_sm)} ${width(thumb_sm_w)}"
                         data-sizes="auto"
                         loading="lazy"
                         alt="${title ? `${title}. ` : ''}Автор проекта: ${author || ''}">
                    <figcaption class="d-flex-column">
                        ${title ? `<h3 class="project-title">${title}</h3>` : ''}
                        ${author ? `<div class="subtitle owner-name">${author}</div>` : ''}
                        <div class="extra d-flex justify-between">
                            ${win_year ? `<div class="portfolio-award d-flex"><svg class="award"><use xlink:href="#award-icon"></use></svg><span>${win_year}</span></div>` : ''}
                            ${average ? `<div class="portfolio-rate d-flex"><span>${average.toFixed(1)}</span><svg class="rate-star"><use xlink:href="#star-icon"></use></svg></div>` : ''}
                        </div>
                    </figcaption>
                </figure>
            </a>`;
    }

    function jsonRequest() {
        if (!nextPage) return;

        preloaderVisible = isInViewport(preloader, true);
        if (!preloaderVisible) return;

        // До завершения запроса на сервере, статус след страницы установим в null, чтобы не выполнять новые ajax запросы
        nextPage = null;

        let url = preloader.href;
        let params = 'page=' + String(currentPage + 1);
        if (filterForm) {
            let filters = createFormData(filterForm);
            params += '&' + filters;
        }
        window.ajaxSend(url, params, 'get', contentRender);
    }

    if (preloader) {
        document.addEventListener('scroll', throttledJsonRequest);
        preloader.addEventListener('click', (e) => {
            e.preventDefault();
            throttledJsonRequest();
        });
        
        throttledJsonRequest();
    }

    // Projects Filter
    const filterForm = document.querySelector('form[name=projects-filter]');
    const contentBlock = document.querySelector('#projects');

    if (filterForm) {
        const filterCheckboxes = filterForm.querySelectorAll('input[type=checkbox]');
        const submitBtn = filterForm.querySelector('[type=submit]');

        // запуск фильтрации контента в селекторе contentBlock
        function submitFilter(el) {
            nextPage = null; // блокируем пролистывание до окончания выполнения запроса в ajaxSend()

            let url = el.action;
            let method = el.method;
            let params = createFormData(el);
            if (params === '') {
                // если аттрибуты сброшены
                contentBlock.classList.remove('filtered');
                submitBtn.disabled = true;
                submitBtn.textContent = 'сбросить фильтры';
            } else {
                contentBlock.classList.add('filtered');
                submitBtn.disabled = false;
                submitBtn.textContent = 'сбросить фильтры';
            }

            document.addEventListener('scroll', throttledJsonRequest);
            window.ajaxSend(url, 'page=1&' + params, method, contentRender);
        }

        // сброс положений аттрибутов фильтра
        function clearCheckboxes() {
            let i = filterCheckboxes.length - 1;
            for (; i >= 0; i--) {
                filterCheckboxes[i].checked = false;
            }
        }

        // загрузка фильтров из URL параметров
        function loadFiltersFromURL() {
            const urlParams = new URLSearchParams(window.location.search);
            const filterGroups = urlParams.getAll('filter-group');

            if (filterGroups.length > 0) {
                filterCheckboxes.forEach((checkbox) => {
                    if (filterGroups.includes(checkbox.value)) {
                        checkbox.checked = true;
                    }
                });
            }
        }

        // проверка наличия активных фильтров при загрузке
        function checkActiveFilters() {
            let hasActiveFilters = false;
            filterCheckboxes.forEach((checkbox) => {
                if (checkbox.checked) {
                    hasActiveFilters = true;
                }
            });
            if (hasActiveFilters) {
                submitBtn.disabled = false;
                contentBlock.classList.add('filtered');
            } else {
                submitBtn.disabled = true;
                contentBlock.classList.remove('filtered');
            }
        }

        // инициализация обработчиков для чекбоксов
        filterCheckboxes.forEach((checkbox) => {
            // повесим событие на изменение чекбокса
            checkbox.addEventListener('change', (e) => {
                submitFilter(filterForm);
            });
        });

        // загрузка фильтров из URL при загрузке страницы
        loadFiltersFromURL();

        // проверка при загрузке страницы
        checkActiveFilters();

        if (filterForm) {
            const hasFilters = Array.from(
                filterForm.querySelectorAll('input[type=checkbox]')
            ).some(cb => cb.checked);

            if (hasFilters) {
                submitFilter(filterForm);
            }
        }


        // нажатие на кнопку сброса фильтров
        filterForm.addEventListener('submit', function (e) {
            e.preventDefault();
            clearCheckboxes();
            submitFilter(this);
        });
    }

});
