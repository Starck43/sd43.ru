import {isInViewport} from './utils/viewport.js';
import {lazyloadInit} from './utils/lazyload.js';
import {createFormData} from "./utils/ajax.js";
import {normalizeMedaPath} from "./utils/common.js";


document.addEventListener("DOMContentLoaded", function () {

    // Projects Render Variables
    let preloader = document.querySelector('#preloader');
    let currentPage = 1, nextPage = true;

    function contentRender(data) {
        const projectsList = data['projects_list'];
        let html = '';

        for (const i in projectsList) {
            const
                id = projectsList[i]['id'],
                title = projectsList[i]['title'],
                thumb_mini = normalizeMedaPath(projectsList[i]['thumb_mini'], data['media_url']),
                thumb_xs = normalizeMedaPath(projectsList[i]['thumb_xs'], data['media_url']),
                thumb_sm = normalizeMedaPath(projectsList[i]['thumb_sm'], data['media_url']),
                thumb_xs_w = projectsList[i]['thumb_xs_w'],
                thumb_sm_w = projectsList[i]['thumb_sm_w'],
                author = projectsList[i]['owner__name'],
                score = (projectsList[i]['average']) ? projectsList[i]['average'].toFixed(1) : null,
                win_year = projectsList[i]['win_year'],
                url = data['projects_url'] + projectsList[i]['owner__slug'] + '/project-' + projectsList[i]['project_id'] + '/';

            html += '<a id="project-' + id + '" class="grid-cell ratio centered" href="' + url + '" title="' + title + '">\
					<figure>\
						<img class="project-cover lazyload"\
							src="' + thumb_mini + '"\
							data-src="' + thumb_sm + '"\
							data-srcset="' + thumb_xs + ' ' + thumb_xs_w + 'w, ' + thumb_sm + ' ' + thumb_sm_w + 'w"\
							loading="lazy"\
							alt="' + (title ? title + '. ' : '') + 'Автор проекта: ' + author + '">\
						<figcaption class="d-flex-column">' +
                (title ? '<h3 class="project-title">' + title + '</h3>' : '') +
                (author ? '<div class="subtitle owner-name">' + author + '</div>' : '') +
                '<div class="extra d-flex justify-between">' +
                (win_year ?
                    '<div class="portfolio-award d-flex">\
                        <svg class="award"><use xlink:href="#award-icon"></use></svg>\
                        <span>' + win_year + '</span>\
							</div>' : '') +
                (score ?
                    '<div class="portfolio-rate d-flex">\
                        <span class="rate-counter">' + score + '</span>\
								<svg class="rate-star"><use xlink:href="#star-icon"></use></svg>\
							</div>' : '') +
                '</div>' +
                '</figcaption>\
            </figure>\
        </a>';
        }

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
            jsonRequest(); // сразу подгрузим следующий контент, если прелоадер остался в зоне видимости
            lazyloadInit(); // обновим lazyload

        } else nextPage = false;


        if (nextPage === false) {
            document.removeEventListener('scroll', jsonRequest);
            preloader.classList.remove('show');
            window.setTimeout(() => {
                preloader.classList.add('hidden');
            }, 200);
        }
    }

    function jsonRequest() {
        if (nextPage && isInViewport(preloader, true)) {
            nextPage = null; // До завершения запроса на сервере, статус след страницы установим в null, чтобы не выполнять новые ajax запросы
            let url = preloader.href;
            let params = 'page=' + String(currentPage + 1);
            if (filterForm) {
                let filters = createFormData(filterForm);
                params += '&' + filters;
            }
            window.ajaxSend(url, params, 'get', contentRender);
        }
    }

    if (preloader) {
        document.addEventListener('scroll', jsonRequest);
        preloader.addEventListener('click', (e) => {
            e.preventDefault();
            jsonRequest();
        });
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

            document.addEventListener('scroll', jsonRequest);
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

        // нажатие на кнопку сброса фильтров
        filterForm.addEventListener('submit', function (e) {
            e.preventDefault();
            clearCheckboxes();
            submitFilter(this);
        });
    }

});
