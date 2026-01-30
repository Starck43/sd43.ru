// Глобальные переменные
let gridContainer = null;

// Функция для обновления состояния кнопки
function updateToggleButton() {
    const toggleBtn = document.getElementById('toggleSelection');
    if (!toggleBtn) return;

    const checkboxes = document.querySelectorAll('.delete-checkbox input[name*="-DELETE"]:not([disabled])');
    const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
    const totalCount = checkboxes.length;

    // Снимаем все классы
    toggleBtn.classList.remove('none-selected', 'some-selected', 'all-selected');

    if (checkedCount === 0) {
        // Ничего не выбрано
        toggleBtn.classList.add('none-selected');
        toggleBtn.querySelector('.btn-text').textContent = 'Выбрать все';
    } else if (checkedCount === totalCount) {
        // Выбраны все
        toggleBtn.classList.add('all-selected');
        toggleBtn.querySelector('.btn-text').textContent = 'Снять все';
    } else {
        // Выбрана часть
        toggleBtn.classList.add('some-selected');
        toggleBtn.querySelector('.btn-text').textContent = `Выбрано ${checkedCount}`;
    }
}

// Функция переключения выбора всех
function toggleAllSelection() {
    const checkboxes = document.querySelectorAll('.delete-checkbox input[name*="-DELETE"]:not([disabled])');
    const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;

    // Если выбраны не все - выбираем все, иначе снимаем все
    const selectAll = checkedCount !== checkboxes.length;

    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll;
        const deleteCheckbox = checkbox.closest('.delete-checkbox');
        const gridItem = checkbox.closest('.image-grid-item');

        if (deleteCheckbox) {
            deleteCheckbox.classList.toggle('checked', selectAll);
        }
        if (gridItem) {
            gridItem.classList.toggle('deleting', selectAll);
        }
    });

    updateToggleButton();
}

function initImagesGrid() {
    gridContainer = document.querySelector('.images-grid-container');
    if (!gridContainer) return;

    // Инициализируем Drag & Drop
    initDragAndDrop();

    gridContainer.addEventListener('click', function (e) {
        // Клик по существующему фото для замены
        const thumbnail = e.target.closest('.image-thumbnail:not(.empty-thumbnail)');
        if (thumbnail && !e.target.closest('.image-actions') && !e.target.closest('input[type="file"]')) {
            const gridItem = thumbnail.closest('.image-grid-item');
            const fileInput = gridItem.querySelector('input[type="file"]');

            if (fileInput) {
                fileInput.click();
                e.stopPropagation();
            }
            return;
        }

        // Клик на "Новое фото" - только если это действительно пустой элемент
        const emptyThumbnail = e.target.closest('.image-thumbnail.empty-thumbnail');
        if (emptyThumbnail && !e.target.closest('input[type="file"]')) {
            const gridItem = emptyThumbnail.closest('.image-grid-item');
            const fileInput = gridItem.querySelector('input[type="file"]');

            if (fileInput) {
                fileInput.click();
                e.stopPropagation();
            }
        }
    });

    gridContainer.addEventListener('change', function (e) {
        if (!e.target.matches('input[type="file"][name^="images-"]')) return;

        const file = e.target.files[0];
        if (!file) return;

        // если это __prefix__
        if (e.target.name.includes('__prefix__')) {
            const realItem = activatePrefixForm(e.target);
            const realInput = realItem.querySelector('input[type="file"][name*="-file"]');

            const dt = new DataTransfer();
            dt.items.add(file);
            realInput.files = dt.files;

            updateImagePreview(realInput);
            addNewEmptyPhotoItem();
            return;
        }

        updateImagePreview(e.target);
    });

    // Отметка для удаления
    gridContainer.addEventListener('click', function (e) {
        const deleteCheckbox = e.target.closest('.delete-checkbox');
        if (!deleteCheckbox) return;

        const djangoCheckbox = deleteCheckbox.querySelector('input[name*="-DELETE"]');
        if (!djangoCheckbox) return;

        const gridItem = deleteCheckbox.closest('.image-grid-item');

        djangoCheckbox.checked = !djangoCheckbox.checked;

        if (djangoCheckbox.checked) {
            deleteCheckbox.classList.add('checked');
            gridItem.classList.add('deleting');
        } else {
            deleteCheckbox.classList.remove('checked');
            gridItem.classList.remove('deleting');
        }

        updateToggleButton();

        e.preventDefault();
        e.stopPropagation();
    });

    const toggleBtn = document.getElementById('toggleSelection');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleAllSelection);
    }

    // Обновляем состояние кнопки при изменении чекбоксов
    gridContainer.addEventListener('change', function (e) {
        if (e.target.matches('input[name*="-DELETE"]')) {
            setTimeout(updateToggleButton, 0); // На след тик event loop
        }
    });

    // Инициализируем кнопку при загрузке
    setTimeout(updateToggleButton, 100);

    // Инициализация атрибута после загрузки
    gridContainer.dataset.initialized = 'true';

    lazyloadInit();
    // Перетаскивание для сортировки (без jQuery)
    initSortableGrid();
}

// Функция для инициализации lazy loading
function lazyloadInit() {
    const gridImages = document.querySelectorAll('.images-grid-container img.lazyload:not(.lazyloaded)');

    if (gridImages.length === 0) return;

    // Для изображений уже с src (загруженных через FileReader) - сразу отмечаем
    gridImages.forEach(img => {
        if (img.src && img.src.startsWith('data:image/')) {
            img.classList.add('lazyloaded');
            img.classList.remove('lazyload');
        }
    });

    // Оставшиеся обрабатываем через IntersectionObserver
    const remainingImages = document.querySelectorAll('.images-grid-container img.lazyload:not(.lazyloaded)');
    if (remainingImages.length === 0) return;

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
            rootMargin: '50px 0px',
            threshold: 0.01
        });

        remainingImages.forEach(img => {
            observer.observe(img);
        });

        // Сохраняем observer для очистки
        window.gridLazyObserver = observer;
    } else {
        remainingImages.forEach(img => {
            loadGridImage(img);
        });
    }
}

function loadGridImage(img) {
    // Если нет src и нет data-src, выходим
    if (!img.src && !img.dataset.src) return;

    // Если есть data-src, устанавливаем его
    if (img.dataset.src && !img.src) {
        img.src = img.dataset.src;
        delete img.dataset.src;
    }

    // Обработчики событий
    const onLoad = () => {
        img.classList.add('lazyloaded');
        img.classList.remove('lazyload');
        img.removeEventListener('load', onLoad);
        img.removeEventListener('error', onError);
    };

    const onError = () => {
        img.classList.add('lazyerror');
        img.classList.remove('lazyload');
        console.warn('Failed to load image:', img.src);
        img.removeEventListener('load', onLoad);
        img.removeEventListener('error', onError);
    };

    // Если изображение уже загружено
    if (img.complete && img.naturalHeight !== 0) {
        onLoad();
    } else {
        img.addEventListener('load', onLoad);
        img.addEventListener('error', onError);

        // Таймаут на случай если события не сработают
        setTimeout(() => {
            if (img.classList.contains('lazyload') && !img.classList.contains('lazyloaded') && !img.classList.contains('lazyerror')) {
                onLoad(); // Предполагаем что загрузилось
            }
        }, 2000);
    }
}

// Инициализация перетаскивания для сортировки
function initSortableGrid() {
    if (!gridContainer) return;

    // Используем нативный подход если нет Sortable.js
    if (typeof Sortable !== 'undefined') {
        new Sortable(gridContainer, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            filter: '.empty-item, .deleting',
            onEnd: updateSortOrder
        });

    } else {
        // Fallback без Sortable.js
        console.log('Sortable.js не загружен, используем упрощенный drag & drop');
    }
}

// Обновление порядка сортировки
function updateSortOrder() {
    const order = [];

    document.querySelectorAll(
        '.image-grid-item[data-image-id]'
    ).forEach(item => {
        order.push(item.dataset.imageId);
    });

    const input = document.getElementById('images-order');
    if (input) {
        input.value = order.join(',');
    }
}

function activatePrefixForm(prefixInput) {
    const gridItem = prefixInput.closest('.image-grid-item');
    const totalForms = document.querySelector('#id_images-TOTAL_FORMS');

    const index = parseInt(totalForms.value, 10);

    gridItem.querySelectorAll('[name]').forEach(el => {
        el.name = el.name.replace('__prefix__', index);
    });

    gridItem.querySelectorAll('[id]').forEach(el => {
        el.id = el.id.replace('__prefix__', index);
    });

    totalForms.value = index + 1;

    // Устанавливаем sort для новой формы
    const sortInput = gridItem.querySelector('input[name*="-sort"]');
    if (sortInput) {
        // Находим максимальный sort
        let maxSort = 0;
        const allSortInputs = document.querySelectorAll('input[name*="-sort"]');
        allSortInputs.forEach(input => {
            if (input !== sortInput) { // не считаем текущий
                const val = parseInt(input.value) || 0;
                if (val > maxSort) maxSort = val;
            }
        });
        sortInput.value = maxSort + 1;
    }

    gridItem.classList.remove('empty-item');
    return gridItem;
}

// Добавление нового пустого элемента для фото
function addNewEmptyPhotoItem() {
    const grid = document.querySelector('.images-grid-container');
    const template = document.querySelector('.empty-form-template');

    if (!grid || !template) return;

    if (grid.querySelector('.image-grid-item.empty-item')) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = template.innerHTML.trim();

    grid.appendChild(wrapper.firstElementChild);
}

// Инициализация Drag & Drop для загрузки файлов
function initDragAndDrop() {
    if (!gridContainer) return;

    // Предотвращаем стандартное поведение
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        gridContainer.addEventListener(eventName, preventDefaults, false);
    });

    // Подсветка области
    ['dragenter', 'dragover'].forEach(eventName => {
        gridContainer.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        gridContainer.addEventListener(eventName, unhighlight, false);
    });

    // Обработка drop
    gridContainer.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight() {
    gridContainer.classList.add('drag-over');
}

function unhighlight() {
    gridContainer.classList.remove('drag-over');
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;

    if (files.length === 0) return;

    // Находим первый пустой элемент
    const emptyThumbnails = document.querySelectorAll('.empty-thumbnail');
    if (emptyThumbnails.length === 0) return;

    // Используем первый файл
    const file = files[0];

    // Проверяем тип файла
    if (!file.type.startsWith('image/')) {
        alert('Пожалуйста, перетащите файл изображения');
        return;
    }

    const emptyThumbnail = emptyThumbnails[0];
    const gridItem = emptyThumbnail.closest('.image-grid-item');
    const fileInput = gridItem.querySelector('input[type="file"]');

    if (fileInput) {
        // Используем DataTransfer для установки файла
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;

        // Триггерим событие change
        const event = new Event('change', {bubbles: true});
        fileInput.dispatchEvent(event);
    }
}

// Функция обновления превью изображения
function updateImagePreview(fileInput) {
    const gridItem = fileInput.closest('.image-grid-item');
    const previewContainer = gridItem.querySelector('.image-container');
    const titleElement = gridItem.querySelector('.image-title');

    if (fileInput.files && fileInput.files[0]) {
        const file = fileInput.files[0];

        // Валидация файла
        if (!file.type.startsWith('image/')) {
            alert('Пожалуйста, выберите файл изображения');
            fileInput.value = '';
            return;
        }

        // Показываем индикатор загрузки
        previewContainer.classList.add('loading');

        // Убираем классы для пустого элемента
        const imageThumbnail = gridItem.querySelector('.image-thumbnail');
        if (imageThumbnail) {
            imageThumbnail.classList.remove('empty-thumbnail');
            previewContainer?.classList.remove('no-image');
        }

        const reader = new FileReader();

        reader.onload = function (e) {
            // Убираем индикатор загрузки
            previewContainer.classList.remove('loading');

            // Создаем новое изображение
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'lazyloaded';
            img.alt = 'Превью загружаемого изображения';

            // Очищаем контейнер
            previewContainer.innerHTML = '';
            previewContainer.appendChild(img);

            // Обновляем название
            const fileName = file.name;
            if (titleElement) {
                const shortName = fileName.length > 20
                    ? fileName.substring(0, 19) + '...'
                    : fileName;
                titleElement.textContent = shortName.toLowerCase();

                // Обновляем поле title если оно пустое
                const titleInput = gridItem.querySelector('input[name*="-title"]');
                if (titleInput && (!titleInput.value || titleInput.value.trim() === '')) {
                    titleInput.value = fileName.replace(/\.[^/.]+$/, "");
                }
            }

            // Обновляем поле filename (если есть)
            const filenameInput = gridItem.querySelector('input[name*="-filename"]');
            if (filenameInput) {
                filenameInput.value = file.name;
            }

            // Обязательно обновляем поле сортировки
            const sortInput = gridItem.querySelector('input[name*="-sort"]');
            if (sortInput) {
                // Устанавливаем максимальный индекс + 1
                const allSortInputs = document.querySelectorAll('input[name*="-sort"]');
                let maxSort = 0;
                allSortInputs.forEach(input => {
                    const val = parseInt(input.value) || 0;
                    if (val > maxSort) maxSort = val;
                });
                sortInput.value = maxSort + 1;
            }

            // Обновляем общий порядок сортировки
            updateSortOrder();
        };

        reader.onerror = function () {
            previewContainer.classList.remove('loading');
            alert('Ошибка при чтении файла');
        };

        reader.readAsDataURL(file);
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(() => {

        // Инициализируем сетку
        initImagesGrid();

    }, 100);
});

export {initImagesGrid};
