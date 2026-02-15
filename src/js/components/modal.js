import {OverlayFactory} from "./overlay.js";

/**
 * Modal component - Модальное окно
 * @typedef {Object} ModalOptions
 * @property {boolean} [useSelfBackdrop]
 */
export class Modal {
    /**
     * @param {HTMLElement|string} modalSelector
     * @param {ModalOptions} [options]
     */
    constructor(modalSelector, options = {}) {
        this.modal = typeof modalSelector === 'string'
            ? document.querySelector(modalSelector)
            : modalSelector;

        if (!this.modal) return;

        // Определяем использовать ли self-backdrop
        const useSelfBackdrop = options.useSelfBackdrop ??
            this.modal.hasAttribute('data-self-backdrop') ??
            true;

        this.overlay = useSelfBackdrop
            ? OverlayFactory.modalWithBackdrop(this.modal)
            : OverlayFactory.modal(this.modal);

        this.isOpen = false;
        this.closeHandlers = [];

        this.initModalSpecific();
        this.initCloseHandlers();
    }

    initModalSpecific() {
        // Обработка data-backdrop атрибута
        const backdropSetting = this.modal.getAttribute('data-backdrop');
        const isStatic = backdropSetting === 'static';

        if (backdropSetting === 'false') {
            this.overlay.options.static = true;
        } else {
            this.overlay.options.static = isStatic;
        }

        // Синхронизация состояния isOpen с overlay
        this.modal.addEventListener('overlay:hidden', () => {
            this.isOpen = false;
            this.modal.dispatchEvent(new CustomEvent('modal:hidden'));
        });
    }

    initCloseHandlers() {
        // Закрытие по кнопкам [data-dismiss="modal"]
        const closeBtns = this.modal.querySelectorAll('[data-dismiss="modal"]');
        closeBtns.forEach(btn => {
            const handler = (e) => {
                e.preventDefault();
                this.close();
            };
            btn.addEventListener('click', handler);
            this.closeHandlers.push({element: btn, handler, type: 'click'});
        });

        // Закрытие по клику на backdrop (для self-backdrop)
        if (this.overlay.options.useSelfAsBackdrop) {
            const backdropHandler = (e) => {
                if (e.target === this.modal && !this.overlay.options.static) {
                    this.close();
                }
            };
            this.modal.addEventListener('click', backdropHandler);
            this.closeHandlers.push({element: this.modal, handler: backdropHandler, type: 'click'});
        }

        // Закрытие по ESC
        const escHandler = (e) => {
            if (e.key === 'Escape' && this.isOpen && !this.overlay.options.static) {
                this.close();
            }
        };
        document.addEventListener('keydown', escHandler);
        this.closeHandlers.push({element: document, handler: escHandler, type: 'keydown'});
    }

    open(data = null) {
        if (this.isOpen) return;

        this.overlay.show();
        this.isOpen = true;

        this.modal.dispatchEvent(new CustomEvent('modal:shown', {
            detail: data
        }));
    }

    close() {
        if (!this.isOpen) return;

        this.overlay.hide();
        this.isOpen = false;

        this.modal.dispatchEvent(new CustomEvent('modal:hidden'));
    }

    destroy() {
        this.closeHandlers.forEach(({element, handler, type}) => {
            element.removeEventListener(type, handler);
        });
        this.closeHandlers = [];

        this.overlay.destroy();
    }

    // Aliases для совместимости
    show() {
        this.open();
    }

    hide() {
        this.close();
    }

    toggle() {
        this.overlay.toggle();
        this.isOpen = !this.isOpen;
    }
}

// Initialize all modals with triggers
export function initModals() {
    const triggers = document.querySelectorAll('[data-toggle="modal"]');

    triggers.forEach(trigger => {
        const targetSelector = trigger.getAttribute('data-target');
        if (!targetSelector) return;

        const target = document.querySelector(targetSelector);
        if (!target) return;

        // Create modal instance if not exists
        if (!window.modalInstances.has(targetSelector)) {
            window.modalInstances.set(targetSelector, new Modal(target, {}));
        }

        trigger.addEventListener('click', (e) => {
            e.preventDefault();

            const openData = {
                trigger: trigger,
                slideIndex: trigger.hasAttribute('data-slide-index')
                    ? parseInt(trigger.getAttribute('data-slide-index'))
                    : Array.from(document.querySelectorAll(`[data-target="${targetSelector}"]`))
                        .indexOf(trigger)
            };

            window.modalInstances.get(targetSelector)?.open(openData);
        });
    });
}

// Функция для очистки при уходе со страницы
export function cleanupModals() {
    if (!window.modalInstances || window.modalInstances.size === 0) return;

    window.modalInstances.forEach(modalInstance => {
        modalInstance.destroy();
    });
    window.modalInstances.clear();
}
