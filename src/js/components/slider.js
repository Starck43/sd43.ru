import Swiper from 'swiper';
import {Autoplay, Keyboard, Navigation, Pagination, Zoom} from 'swiper/modules';

import 'swiper/css';
import 'swiper/css/zoom';
import 'swiper/css/autoplay';
import 'swiper/css/keyboard';

import {isMobile} from "../utils/common.js";

/**
 * @typedef {'banner' | 'gallery' | 'slider'} SwiperType
 */

/**
 * Базовые настройки для разных типов слайдеров
 */
const getSwiperConfig = (type, slidesCount = Infinity) => {
    const baseConfig = {
        modules: [Keyboard, Navigation],
        lazy: true,
        lazyPreloadPrevNext: 3,
        speed: 500,
        keyboard: {
            enabled: true,
            onlyInViewport: true,
        },
    };

    const typeConfigs = {
        banner: {
            modules: [Navigation, Pagination, Keyboard, Autoplay],
            loop: slidesCount > 1, // Отключаем loop если только один слайд
            slidesPerView: 1,
            spaceBetween: 0,
            speed: Math.round(window.innerWidth / 1.5),
            autoplay: slidesCount > 1 ? { // Отключаем autoplay для одного слайда
                delay: 5000,
                disableOnInteraction: true,
            } : false,
            on: {
                afterInit: function (swiper) {
                    swiper.el.classList.add('show');
                }
            }
        },
        slider: {
            modules: [Navigation, Pagination, Keyboard, Autoplay],
            loop: slidesCount > 1, // Отключаем loop если недостаточно слайдов
            slidesPerView: 1,
            spaceBetween: 0,
            breakpoints: {
                992: {slidesPerView: Math.min(2, slidesCount), spaceBetween: 16},
                1400: {slidesPerView: Math.min(3, slidesCount), spaceBetween: 24},
            },
            autoplay: slidesCount > 1 ? { // Отключаем autoplay для одного слайда
                delay: 4000,
                disableOnInteraction: true,
            } : false,
            on: {
                afterInit: function (swiper) {
                    swiper.el.classList.add('show');
                }
            }
        },
        gallery: {
            modules: [Navigation, Pagination, Keyboard, Zoom],
            loop: false,
            speed: 300,
            zoom: isMobile ? {maxRatio: 3, minRatio: 1} : false,
        }
    };

    return {
        ...baseConfig,
        ...typeConfigs[type],
    };
};

/**
 * Инициализирует Swiper для контейнера
 */
export function initSwiper(container, type = 'gallery', customOptions = {}) {
    const el = typeof container === 'string' ? document.querySelector(container) : container;
    if (!el) return null;

    const wrapper = el.querySelector('.swiper-wrapper');
    if (!wrapper) return null;

    // Гарантируем базовые классы
    if (!el.classList.contains('swiper')) {
        el.classList.add('swiper');
    }

    // Считаем количество слайдов
    const slidesCount = wrapper.querySelectorAll('.swiper-slide:not(.swiper-slide-duplicate)').length;

    // Определяем, нужно ли показывать навигацию и пагинацию
    const hasMultipleSlides = slidesCount > 1;
    const hasPagination = el.querySelector('.swiper-pagination') && hasMultipleSlides;
    const hasNavigation = el.querySelector('.arrow-right') && el.querySelector('.arrow-left') && hasMultipleSlides;

    const config = {
        ...getSwiperConfig(type, slidesCount),
        ...customOptions,
        pagination: hasPagination ? {
            el: el.querySelector('.swiper-pagination'),
            clickable: true,
        } : false,
        navigation: hasNavigation ? {
            nextEl: el.querySelector('.arrow-right'),
            prevEl: el.querySelector('.arrow-left'),
        } : false,
    };

    // Для случаев, когда пользовательские настройки переопределяют loop
    if (customOptions.loop !== undefined) {
        config.loop = customOptions.loop;
    } else if (config.loop && !hasMultipleSlides) {
        // Гарантируем отключение loop если только один слайд
        config.loop = false;
    }

    const instance = new Swiper(el, config);

    // Обновляем после создания для корректного расчета размеров
    setTimeout(() => {
        instance.update();
    }, 50);

    return instance;
}

/**
 * Инициализирует или обновляет Swiper с указанным индексом
 */
export function getSwiper(swiperInstance, container, type = 'gallery', slideIndex = 0, customOptions = {}) {
    if (!swiperInstance) {
        swiperInstance = initSwiper(container, type, {
            initialSlide: slideIndex,
            ...customOptions
        });
        return swiperInstance;
    } else {
        swiperInstance.slideTo(slideIndex, 0);
        return swiperInstance;
    }
}

/**
 * Инициализирует модальную галерею с ленивой загрузкой
 */
function initLazyGallery(gallery) {
    let gallerySwiper = null;
    const galleryId = '#' + gallery.id;
    let cleanupTimeout = null;

    const openSlide = (slideIndex = 0) => {
        // Очищаем предыдущий таймаут, если есть
        if (cleanupTimeout) {
            clearTimeout(cleanupTimeout);
            cleanupTimeout = null;
        }

        // Всегда пересоздаем Swiper для гарантии корректной работы
        if (gallerySwiper) {
            gallerySwiper.destroy(true, true);
            gallerySwiper = null;
        }

        gallerySwiper = getSwiper(gallerySwiper, gallery, 'gallery', slideIndex);

        // Обновляем после полного отображения модалки
        gallery.addEventListener('transitionend', function onTransitionEnd() {
            gallery.removeEventListener('transitionend', onTransitionEnd);
            if (gallerySwiper) {
                gallerySwiper.update();
                gallerySwiper.slideTo(slideIndex, 0);
            }
        }, {once: true});
    };

    // Если modal.js инициализировал модальное окно
    if (window.modalInstances?.has(galleryId)) {
        gallery.addEventListener('modal:shown', (e) => {
            const slideIndex = e.detail?.slideIndex ?? 0;
            openSlide(slideIndex);
        });

        // Cleanup при закрытии модалки
        gallery.addEventListener('modal:hidden', () => {
            if (gallerySwiper) {
                // ВАЖНО: Не уничтожаем Swiper сразу, а ждем завершения анимации закрытия.
                // Устанавливаем таймаут чуть больше чем длительность анимации
                cleanupTimeout = setTimeout(() => {
                    if (gallerySwiper) {
                        gallerySwiper.destroy(true, true);
                        gallerySwiper = null;
                    }
                    cleanupTimeout = null;
                }, 300);
            }
        });
    }
    // Fallback - если modal.js не подключен
    else {
        const triggers = document.querySelectorAll(`[data-toggle="modal"][data-target="${galleryId}"]`);

        triggers.forEach((trigger, index) => {
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                const slideIndex = trigger.dataset.slideIndex ? parseInt(trigger.dataset.slideIndex) : index;
                openSlide(slideIndex);

                gallery.classList.add('show');
                document.body.classList.add('modal-open');
            });
        });

        // Обработка закрытия
        gallery.querySelectorAll('[data-dismiss="modal"]').forEach(btn => {
            btn.addEventListener('click', () => {
                gallery.classList.remove('show');
                document.body.classList.remove('modal-open');

                if (gallerySwiper) {
                    gallerySwiper.destroy(true, true);
                    gallerySwiper = null;
                }
            });
        });
    }

    return () => {
        if (gallerySwiper) {
            gallerySwiper.destroy(true, true);
        }
    };
}

/**
 * Инициализирует обычный слайдер (немедленно)
 */
function initEagerSlider(container, type) {
    return initSwiper(container, type);
}

/**
 * Основная функция инициализации всех слайдеров
 * @param {string|string[]} [types] - конкретные типы для инициализации (опционально)
 */
export function initSliders(types = null) {
    const instances = [];
    const cleanupCallbacks = [];

    let selector = '[data-swiper-type]';
    if (types) {
        const typeFilters = Array.isArray(types) ? types : [types];
        const typeSelectors = typeFilters.map(type => `[data-swiper-type="${type}"]`);
        selector = typeSelectors.join(', ');
    }

    const sliders = document.querySelectorAll(selector);

    sliders.forEach(container => {
        const type = container.dataset.swiperType || 'gallery';

        // Для модальных галерей пропускаем проверку видимости
        const isModalGallery = type === 'gallery' && container.classList.contains('modal');

        const isEagerSlider = ['slider', 'banner'].includes(type);

        const style = window.getComputedStyle(container);
        const isHidden = !isModalGallery && !isEagerSlider &&
            (style.display === 'none' || style.visibility === 'hidden');

        if (isHidden) return;

        if (isModalGallery) {
            const cleanup = initLazyGallery(container);
            cleanupCallbacks.push(cleanup);
        } else {
            const instance = initEagerSlider(container, type);
            if (instance) instances.push(instance);
        }
    });

    // Очистка при уходе со страницы
    window.addEventListener('beforeunload', () => {
        cleanupCallbacks.forEach(cleanup => cleanup());
    });

    return instances;
}
