/**
 * Navbar component - handles navbar-specific functionality
 */

import {Offcanvas} from "./offcanvas.js";

export class Navbar {
    constructor(navbarElement) {
        this.navbar = navbarElement;
        if (!this.navbar) return;

        this.menu = document.querySelector('#navbarMenu');
        this.menuOffcanvas = this.menu ? new Offcanvas(this.menu) : null;

        this.init();
    }

    init() {
        navbarOffset(this.navbar);
        this.initNavLinks();
        initExhibitionsMenu();
        this.initResizeHandler();
    }

    initNavLinks() {
        const navLinks = document.querySelectorAll('a.nav-link:not(.dropdown-toggle)');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 992 && this.menuOffcanvas) {
                    this.menuOffcanvas.hide();
                }
            });
        });
    }

    initResizeHandler() {
        window.addEventListener('resize', () => {
            if (window.innerWidth >= 992) {
                const isDesignerPage = document.documentElement.classList.contains('designer-page') ||
                    document.body.classList.contains('designer-page');

                if (!isDesignerPage && this.menuOffcanvas && this.menu.classList.contains('show')) {
                    this.menuOffcanvas.hide();
                }
                navbarOffset(this.navbar);
            }
        });
    }
}

/**
 * Инициализация меню выставок
 * Для десктопа (>=992px): прямой переход на /exhibitions/
 * Для мобильной (<992px): раскрытие dropdown списка с годами
 */
export function initExhibitionsMenu() {
    const exhibitionsLink = document.getElementById('exhibitionsMenuLink');
    const dropdownList = document.getElementById('dropdownYearsList');

    if (!exhibitionsLink || !dropdownList) return;

    exhibitionsLink.addEventListener('click', (e) => {
        // Для мобильной версии - toggle dropdown
        if (window.innerWidth < 992) {
            e.preventDefault();

            const isNotExpanded = (exhibitionsLink.getAttribute('aria-expanded') !== 'true').toString();
            exhibitionsLink.setAttribute('aria-expanded', isNotExpanded);

            if (isNotExpanded) {
                dropdownList.classList.add('show');
                dropdownList.classList.remove('collapse');
            } else {
                dropdownList.classList.remove('show');
                dropdownList.classList.add('collapse');
            }
        }
    });
}

/**
 * Вычисление высоты блоков навигации, заголовка, и контейнера
 * @param {HTMLElement} elem - элемент навигации
 */
export function navbarOffset(elem) {
    if (!elem) return;

    const navHeight = elem.clientHeight;

    // Добавим смещение следующему после меню элементу
    const header = elem.nextElementSibling;
    if (header) {
        //header.style.marginTop = navHeight + 'px';
        const headerHeight = header.clientHeight;

        const container = header.nextElementSibling;
        if (container) {
            container.style.minHeight = `calc(100vh - ${navHeight}px - ${headerHeight}px)`;
        }
    }
}

