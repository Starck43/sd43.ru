/**
 * Accordion component - toggle visibility of content sections
 */
// Простой вариант с явным data-id
export class Accordion {
    constructor(element) {
        this.element = element;
        this.id = element.dataset.accordionId ||
            element.querySelector('h3, h2')?.textContent?.trim() ||
            'accordion-' + Math.random().toString(36).substring(2, 9);

        this.init();
    }

    init() {
        const children = Array.from(this.element.children);
        this.header = children.find(el => !el.hasAttribute('data-static'));
        this.content = children.filter(el =>
            el !== this.header && !el.hasAttribute('data-static')
        );

        if (!this.header || !this.content.length) return;

        // Проверяем сохраненное состояние
        const savedState = sessionStorage.getItem(this.id);

        // Определяем начальное состояние
        this.isExpanded = savedState === 'expanded' || this.element.dataset.accordion === 'expanded';

        this.element.dataset.accordion = this.isExpanded ? 'expanded' : 'collapsed';
        this.updateHeight();

        this.header.addEventListener('click', (e) => this.toggle(e));
    }

    toggle(e) {
        if (e.target.closest('a, [data-static]')) return;
        e.preventDefault();

        this.isExpanded = !this.isExpanded;
        this.element.dataset.accordion = this.isExpanded ? 'expanded' : 'collapsed';
        this.updateHeight();

        // Сохраняем в sessionStorage (живет до закрытия вкладки)
        sessionStorage.setItem(this.id, this.isExpanded ? 'expanded' : 'collapsed');
    }

    updateHeight() {
        this.content.forEach(el => {
            el.style.height = this.isExpanded ? el.scrollHeight + 'px' : '0';
            el.style.opacity = this.isExpanded ? '1' : '0';
        });
    }
}
