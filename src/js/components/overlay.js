/**
 * Универсальный класс для управления overlay элементами
 *
 * @typedef {Object} OverlayOptions
 * @property {string} [backdropClass]
 * @property {string} [bodyClass]
 * @property {boolean} [backdrop]
 * @property {boolean} [keyboard]
 * @property {boolean} [static]
 * @property {boolean} [useSelfAsBackdrop]
 */
export class Overlay {
    /**
     * @param {HTMLElement|string} targetElement
     * @param {OverlayOptions} [options]
     */
    constructor(targetElement, options = {}) {
        this.target = typeof targetElement === 'string'
            ? document.querySelector(targetElement)
            : targetElement;

        if (!this.target) return;

        this.options = {
            backdropClass: 'overlay-backdrop',
            bodyClass: 'overlay-open',
            backdrop: true,
            keyboard: true,
            static: false,
            useSelfAsBackdrop: false,
            ...options
        };

        this.isOpen = false;
        this.backdrop = null;
        this.closeHandlers = [];

        if (!window.openOverlays) window.openOverlays = new Set();

        this.init();
    }

    init() {
        // Создаем/получаем backdrop
        if (this.options.backdrop) {
            this.createBackdrop();
        }

        // Находим кнопки закрытия внутри target
        const closeButtons = this.target.querySelectorAll('[data-dismiss]');
        closeButtons.forEach(btn => {
            const handler = (e) => {
                e.preventDefault();
                this.hide();
            };
            btn.addEventListener('click', handler);
            this.closeHandlers.push({element: btn, handler, type: 'click'});
        });

        // Закрытие по клику на backdrop
        if (this.backdrop) {
            const backdropHandler = (e) => {
                // Для self-backdrop проверяем клик по самому target
                if (this.options.useSelfAsBackdrop) {
                    if (e.target === this.target && !this.options.static) {
                        this.hide();
                    }
                }
                // Для внешнего backdrop проверяем клик по backdrop
                else if (e.target === this.backdrop && !this.options.static) {
                    this.hide();
                }
            };

            const backdropElement = this.options.useSelfAsBackdrop ? this.target : this.backdrop;
            backdropElement.addEventListener('click', backdropHandler);
            this.closeHandlers.push({element: backdropElement, handler: backdropHandler, type: 'click'});
        }

        // Закрытие по ESC
        if (this.options.keyboard) {
            const escHandler = (e) => {
                if (e.key === 'Escape' && this.isOpen && !this.options.static) {
                    this.hide();
                }
            };
            document.addEventListener('keydown', escHandler);
            this.closeHandlers.push({element: document, handler: escHandler, type: 'keydown'});
        }
    }

    createBackdrop() {
        if (this.options.useSelfAsBackdrop) {
            // Используем сам target как backdrop
            this.backdrop = this.target;
        } else {
            // Ищем существующий backdrop с таким классом
            this.backdrop = document.querySelector(`.${this.options.backdropClass}`);

            if (!this.backdrop) {
                this.backdrop = document.createElement('div');
                this.backdrop.className = this.options.backdropClass;
                document.body.appendChild(this.backdrop);
            }
        }
    }

    show() {
        if (this.isOpen) return;

        this.isOpen = true;
        this.target.classList.add('show');

        if (this.backdrop && !this.options.useSelfAsBackdrop) {
            this.backdrop.classList.add('show');
            this.backdrop.dataset.activeOverlay = this.target.id || this.target.className;
        }

        document.body.classList.add(this.options.bodyClass);
        document.body.style.overflow = 'hidden';

        this.target.dispatchEvent(new CustomEvent('overlay:shown'));
        window.openOverlays.add(this.target);
    }

    hide() {
        if (!this.isOpen) return;

        this.isOpen = false;
        this.target.classList.remove('show');

        // Скрываем backdrop только если это внешний backdrop
        if (this.backdrop && !this.options.useSelfAsBackdrop && !this.hasOtherOpenOverlays()) {
            this.backdrop.classList.remove('show');
        }

        // Очищаем метку активного overlay
        if (this.backdrop && !this.options.useSelfAsBackdrop) {
            delete this.backdrop.dataset.activeOverlay;
        }

        const transitionEndHandler = () => {
            this.target.removeEventListener('transitionend', transitionEndHandler);

            if (!this.hasOtherOpenOverlays()) {
                document.body.classList.remove(this.options.bodyClass);
                document.body.style.overflow = '';
            }

            this.target.dispatchEvent(new CustomEvent('overlay:hidden'));
        };

        this.target.addEventListener('transitionend', transitionEndHandler, {once: true});

        // Fallback
        setTimeout(() => {
            this.target.removeEventListener('transitionend', transitionEndHandler);

            if (!this.hasOtherOpenOverlays()) {
                document.body.classList.remove(this.options.bodyClass);
                document.body.style.overflow = '';
            }

            this.target.dispatchEvent(new CustomEvent('overlay:hidden'));
        }, 200);

        window.openOverlays.delete(this.target);
    }

    /**
     * Проверяет, есть ли другие открытые overlays
     */
    hasOtherOpenOverlays() {
        return window.openOverlays.size > 1 ||
            (window.openOverlays.size === 1 && !window.openOverlays.has(this.target));
    }

    toggle() {
        if (this.isOpen) {
            this.hide();
        } else {
            this.show();
        }
    }

    destroy() {
        this.closeHandlers.forEach(({element, handler, type}) => {
            element.removeEventListener(type, handler);
        });
        this.closeHandlers = [];

        // Удаляем backdrop только если он внешний и создан нами
        if (this.backdrop && !this.options.useSelfAsBackdrop && this.backdrop.parentNode) {
            // Проверяем, не используется ли backdrop другими overlay
            if (!this.backdrop.dataset.activeOverlay) {
                this.backdrop.parentNode.removeChild(this.backdrop);
            }
        }
    }
}

/**
 * Фабрика для создания overlay с предустановленными настройками
 */
export const OverlayFactory = {
    // Для offcanvas элементов - внешний backdrop
    offcanvas(target) {
        return new Overlay(target, {
            backdropClass: 'offcanvas-backdrop',
            bodyClass: 'offcanvas-open',
            backdrop: true,
            useSelfAsBackdrop: false
        });
    },

    // Для modal элементов - self-backdrop (использует сам modal как backdrop)
    modal(target) {
        return new Overlay(target, {
            bodyClass: 'modal-open',
            backdrop: false,
            useSelfAsBackdrop: true
        });
    },

    // Для modal элементов с внешним backdrop (альтернатива)
    modalWithBackdrop(target) {
        return new Overlay(target, {
            backdropClass: 'modal-backdrop',
            bodyClass: 'modal-open',
            backdrop: true,
            useSelfAsBackdrop: false
        });
    },

    // Для collapse элементов - без backdrop
    collapse(target) {
        return new Overlay(target, {
            backdrop: false,
            bodyClass: 'collapse-open'
        });
    }
};
