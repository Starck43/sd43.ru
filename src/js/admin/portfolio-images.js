import {lazyloadInit} from '../utils/lazyload.js';

// Функция инициализации grid изображений
function initImagesGrid() {
    const gridContainer = document.querySelector('.images-grid-container');
    if (!gridContainer) return;

    // Клик по существующему фото для замены
    gridContainer.addEventListener('click', function (e) {
        const thumbnail = e.target.closest('.image-thumbnail:not(.empty-thumbnail)');
        if (!thumbnail || e.target.closest('.image-actions')) return;

        const gridItem = thumbnail.closest('.image-grid-item');
        const fileInput = gridItem.querySelector('input[type="file"]');

        if (fileInput) {
            fileInput.click();
        }
    });

    // Клик на "Новое фото" для добавления файла
    gridContainer.addEventListener('click', function (e) {
        const emptyThumbnail = e.target.closest('.empty-thumbnail');
        if (!emptyThumbnail) return;

        const gridItem = emptyThumbnail.closest('.image-grid-item');
        const fileInput = gridItem.querySelector('input[type="file"]');

        if (fileInput) {
            fileInput.click();
        }
    });

    // Обработка выбора файла
    gridContainer.addEventListener('change', function (e) {
        if (e.target.matches('input[type="file"]')) {
            updateImagePreview(e.target);

            // Если это было пустое фото, обновляем его внешний вид
            const gridItem = e.target.closest('.image-grid-item');
            const emptyThumbnail = gridItem.querySelector('.empty-thumbnail');
            if (emptyThumbnail) {
                emptyThumbnail.classList.remove('empty-thumbnail');
            }
        }
    });

    // Отметка для удаления
    gridContainer.addEventListener('click', function (e) {
        const deleteCheckbox = e.target.closest('.delete-checkbox');
        if (!deleteCheckbox) return;

        // Находим чекбокс Django
        const djangoCheckbox = deleteCheckbox.querySelector('input[name*="-DELETE"]');
        if (!djangoCheckbox) return;

        const gridItem = deleteCheckbox.closest('.image-grid-item');

        // Переключаем состояние Django чекбокса
        djangoCheckbox.checked = !djangoCheckbox.checked;

        if (djangoCheckbox.checked) {
            deleteCheckbox.classList.add('checked');
            gridItem.classList.add('deleting');

            // Отключаем required поля для удаляемых элементов
            gridItem.querySelectorAll('input[required], select[required], textarea[required]').forEach(input => {
                if (!input.dataset.originalRequired) {
                    input.dataset.originalRequired = 'true';
                }
                input.required = false;
            });
        } else {
            deleteCheckbox.classList.remove('checked');
            gridItem.classList.remove('deleting');

            // Восстанавливаем required поля
            gridItem.querySelectorAll('[data-original-required]').forEach(input => {
                input.required = true;
                delete input.dataset.originalRequired;
            });
        }

        e.preventDefault();
        e.stopPropagation();
    });

    // Кнопки "Выбрать все" / "Снять выделение"
    const selectAllBtn = document.getElementById('selectAllImages');
    const deselectAllBtn = document.getElementById('deselectAllImages');

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function () {
            const checkboxes = document.querySelectorAll('.delete-checkbox input[name*="-DELETE"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = true;
                const deleteCheckbox = checkbox.closest('.delete-checkbox');
                const gridItem = checkbox.closest('.image-grid-item');
                if (deleteCheckbox) deleteCheckbox.classList.add('checked');
                if (gridItem) {
                    gridItem.classList.add('deleting');
                }
            });
        });
    }

    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', function () {
            const checkboxes = document.querySelectorAll('.delete-checkbox input[name*="-DELETE"]');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
                const deleteCheckbox = checkbox.closest('.delete-checkbox');
                const gridItem = checkbox.closest('.image-grid-item');
                if (deleteCheckbox) deleteCheckbox.classList.remove('checked');
                if (gridItem) {
                    gridItem.classList.remove('deleting');
                }
            });
        });
    }

    // Инициализируем lazy loading для всех изображений в grid
    initGridLazyload();
}

// Функция для инициализации lazy loading только в grid
function initGridLazyload() {
    const gridImages = document.querySelectorAll('.images-grid-container img.lazyload:not(.lazyloaded)');

    if (gridImages.length === 0) return;

    // Используем тот же подход что и в lazyload.js
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    loadGridImage(img);
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '100px 0px',
            threshold: 0.01
        });

        gridImages.forEach(img => {
            observer.observe(img);
        });
    } else {
        gridImages.forEach(img => {
            loadGridImage(img);
        });
    }
}

// Упрощенная функция загрузки изображения для grid
function loadGridImage(img) {
    if (!img.dataset.src) return;

    const src = img.dataset.src;
    delete img.dataset.src;

    img.src = src;

    img.addEventListener('load', () => {
        img.classList.add('lazyloaded');
        img.classList.remove('lazyload');
    });

    img.addEventListener('error', () => {
        img.classList.add('lazyerror');
        img.classList.remove('lazyload');
    });
}

// Функция обновления превью изображения
function updateImagePreview(fileInput) {
    const gridItem = fileInput.closest('.image-grid-item');
    const previewContainer = gridItem.querySelector('.image-container');
    const titleElement = gridItem.querySelector('.image-title');

    if (fileInput.files && fileInput.files[0]) {
        const reader = new FileReader();

        reader.onload = function (e) {
            // Создаем новое изображение
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'lazyloaded'; // Сразу загружено, поэтому lazyloaded
            img.style.opacity = '1';
            img.alt = 'Preview';

            // Очищаем контейнер и добавляем новое изображение
            previewContainer.innerHTML = '';
            previewContainer.appendChild(img);

            // Обновляем название если есть
            const fileName = fileInput.files[0].name;
            if (titleElement) {
                const shortName = fileName.length > 20
                    ? fileName.substring(0, 17) + '...'
                    : fileName;
                titleElement.textContent = shortName.toLowerCase();

                // Обновляем поле title в форме если оно есть
                const titleInput = gridItem.querySelector('input[name*="-title"], input[id*="-title"]');
                if (titleInput && !titleInput.value) {
                    titleInput.value = fileName
                }
            }

            // Добавляем индикатор нового файла
            gridItem.classList.add('has-new-file');
        };

        reader.readAsDataURL(fileInput.files[0]);
    }
}

// Переинициализация после добавления новых форм
function reinitImagesGrid() {
    // Очищаем текущие слушатели и инициализируем заново
    initImagesGrid();
}

// Обработка добавления новых форм (с использованием jQuery который есть в админке)
function setupFormsetHandlers() {
    // Используем MutationObserver для отслеживания добавления новых форм
    const gridContainer = document.querySelector('.images-grid-container');
    if (!gridContainer) return;

    const observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.addedNodes.length > 0) {
                // Проверяем, были ли добавлены новые элементы grid
                const addedItems = Array.from(mutation.addedNodes).filter(node =>
                    node.classList && node.classList.contains('image-grid-item')
                );

                if (addedItems.length > 0) {
                    setTimeout(reinitImagesGrid, 100);
                }
            }

            if (mutation.removedNodes.length > 0) {
                setTimeout(reinitImagesGrid, 100);
            }
        });
    });

    observer.observe(gridContainer, {
        childList: true,
        subtree: true
    });
}


document.addEventListener('DOMContentLoaded', function () {
    // Инициализация общего lazy loading
    lazyloadInit();

    // Инициализация grid изображений
    initImagesGrid();

    // Настройка обработчиков для динамических форм
    setupFormsetHandlers();

});

export {initImagesGrid};
