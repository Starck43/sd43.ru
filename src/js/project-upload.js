import {Modal} from './components/modal.js';

document.addEventListener("DOMContentLoaded", () => {
    const modalContainer = document.getElementById('progressModal');
    const form = document.querySelector('#uploadProjectForm');
    const isEditMode = window.location.pathname.includes('/portfolio/edit/');

    if (!form) return;

    const exhibition = form.querySelector('select[name=exhibition]');
    const owner = form.querySelector('select[name=owner]');
    const nominations = form.querySelector('select[name=nominations]');
    const categories = form.querySelector('select[name=categories]');
    const nominationsField = form.querySelector('.field-nominations');
    const categoriesField = form.querySelector('.field-categories');
    const attributes = form.querySelector('.field-attributes');
    const images = form.querySelectorAll('.field-images img');
    const files = form.querySelector('input[name=files]');


    // Сохраняем начальные значения для редактирования
    const initialValues = {
        exhibition: exhibition?.value || '',
        owner: owner?.value || '',
        nominations: nominations?.selectedOptions ?
            Array.from(nominations.selectedOptions).map(opt => opt.value) : [],
        categories: categories?.selectedOptions ?
            Array.from(categories.selectedOptions).map(opt => opt.value) : []
    };

    // 1. Инициализация видимости полей
    function initFieldVisibility() {
        if (!exhibition) return;

        if (exhibition.value === "") {
            nominationsField?.classList.add('hidden');
            attributes?.classList.add('hidden');
            if (owner) owner.closest('.form-group')?.classList.remove('hidden');
        } else {
            categoriesField?.classList.add('hidden');
            if (owner) owner.closest('.form-group')?.classList.add('hidden');
        }
    }

    // 2. Загрузка маппинга номинаций → категории
    let nominationsToCategories = {};

    function loadNominationsCategoriesMapping() {
        return fetch('/api/nominations-categories-mapping/')
            .then(response => response.json())
            .then(data => {
                nominationsToCategories = data || {};
                console.log('Nominations mapping loaded:', nominationsToCategories);
            })
            .catch(error => {
                console.error('Error loading nominations mapping:', error);
            });
    }

    // 3. Автоматический выбор категорий по номинациям
    function updateCategoriesFromNominations() {
        if (!categories) return;

        const selectedNominations = Array.from(nominations?.selectedOptions || []).map(opt => opt.value);
        const selectedCategories = new Set();

        selectedNominations.forEach(nominationId => {
            const categoryId = nominationsToCategories[nominationId];
            if (categoryId && categoryId !== 'None' && categoryId !== 'null') {
                selectedCategories.add(categoryId);
            }
        });

        // Устанавливаем выбранные категории
        Array.from(categories.options).forEach(option => {
            option.selected = selectedCategories.has(option.value);
        });

        // Для Select2
        if (typeof jQuery !== 'undefined' && categories.classList.contains('select2-hidden-accessible')) {
            $(categories).trigger('change.select2');
        }
    }

    // 4. Загрузка выставок по участнику (для админки/редактирования)
    function loadExhibitionsByOwner(ownerId) {
        if (!exhibition || !ownerId) return;

        exhibition.disabled = true;
        exhibition.innerHTML = '<option value="">Загрузка выставок...</option>';

        fetch(`/api/get-exhibitions-by-owner/?owner_id=${ownerId}`)
            .then(response => response.json())
            .then(data => {
                exhibition.innerHTML = '<option value="">-- Выберите выставку --</option>';

                if (data.exhibitions && data.exhibitions.length > 0) {
                    data.exhibitions.forEach(exh => {
                        const option = document.createElement('option');
                        option.value = exh.id;
                        option.textContent = exh.title;

                        // Восстанавливаем выбранную выставку при редактировании
                        if (initialValues.exhibition === String(exh.id)) {
                            option.selected = true;
                        }

                        exhibition.appendChild(option);
                    });
                } else {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'Нет доступных выставок';
                    option.disabled = true;
                    exhibition.appendChild(option);
                }

                exhibition.disabled = false;

                // Если выставка была выбрана, загружаем ее номинации
                if (initialValues.exhibition) {
                    loadNominationsForExhibition(initialValues.exhibition);
                }
            })
            .catch(error => {
                console.error('Error loading exhibitions:', error);
                exhibition.innerHTML = '<option value="">Ошибка загрузки</option>';
            });
    }

    // 5. Загрузка номинаций по выставке
    function loadNominationsForExhibition(exhibitionId) {
        if (!nominations || !exhibitionId) return;

        nominations.disabled = true;
        nominations.innerHTML = '<option value="">Загрузка номинаций...</option>';

        // Передаем выбранные номинации для восстановления
        const selectedIds = initialValues.nominations.join(',');

        fetch(`/api/get-nominations/?exhibition_id=${exhibitionId}&selected=${selectedIds}`)
            .then(response => response.json())
            .then(data => {
                nominations.innerHTML = '';

                if (data.nominations && data.nominations.length > 0) {
                    data.nominations.forEach(nom => {
                        const option = document.createElement('option');
                        option.value = nom.id;
                        option.textContent = nom.title;

                        // Восстанавливаем выбранные номинации
                        if (initialValues.nominations.includes(String(nom.id)) ||
                            nom.selected === true) {
                            option.selected = true;
                        }

                        nominations.appendChild(option);
                    });

                    nominationsField?.classList.remove('hidden');
                    updateCategoriesFromNominations();
                } else {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = 'Нет доступных номинаций';
                    option.disabled = true;
                    nominations.appendChild(option);
                }

                nominations.disabled = false;

                // Для Select2
                if (typeof jQuery !== 'undefined' && nominations.classList.contains('select2-hidden-accessible')) {
                    $(nominations).trigger('change.select2');
                }
            })
            .catch(error => {
                console.error('Error loading nominations:', error);
                nominations.innerHTML = '<option value="">Ошибка загрузки</option>';
            });
    }

    // 6. Инициализация всех обработчиков
    function initAllHandlers() {
        // Инициализация видимости
        initFieldVisibility();

        // Загружаем маппинг номинаций-категорий
        loadNominationsCategoriesMapping().then(() => {
            // Если в режиме редактирования и есть владелец, загружаем его выставки
            if (isEditMode && owner && owner.value) {
                loadExhibitionsByOwner(owner.value);
            }

            // Если выставка уже выбрана при загрузке
            if (exhibition && exhibition.value) {
                loadNominationsForExhibition(exhibition.value);
            }
        });

        // Обработчик изменения выставки
        exhibition?.addEventListener('change', (e) => {
            const value = e.target.value;

            if (value) {
                nominationsField?.classList.remove('hidden');
                attributes?.classList.remove('hidden');
                categoriesField?.classList.add('hidden');
                if (owner) owner.closest('.form-group')?.classList.add('hidden');

                loadNominationsForExhibition(value);
            } else {
                categoriesField?.classList.remove('hidden');
                attributes?.classList.add('hidden');
                nominationsField?.classList.add('hidden');
                if (owner) owner.closest('.form-group')?.classList.remove('hidden');

                if (nominations) {
                    nominations.innerHTML = '<option value="">-- Сначала выберите выставку --</option>';
                }
            }
        });

        // Обработчик изменения владельца (для админки)
        owner?.addEventListener('change', (e) => {
            if (e.target.value) {
                loadExhibitionsByOwner(e.target.value);
            } else {
                exhibition.innerHTML = '<option value="">-- Сначала выберите участника --</option>';
            }
        });

        // Обработчик изменения номинаций (обновляем категории)
        nominations?.addEventListener('change', updateCategoriesFromNominations);
    }

    // Запускаем инициализацию
    initAllHandlers();

    // Обработчик выбора изображений
    images.forEach((image) => {
        image.addEventListener('click', (e) => {
            e.target.parentNode.classList.toggle('selected');
        });
    });

    // Предварительный просмотр выбранных изображений
    files?.addEventListener('change', (e) => {
        const selectedFiles = e.target.files;
        if (selectedFiles.length > 0) {
            console.log('Выбрано файлов:', selectedFiles.length);
            showFilePreview(selectedFiles);
        }
    });

    // Обработчик отправки формы
    form.addEventListener('submit', (e) => {
        e.preventDefault()

        if (!isEditMode) {
            showModal('0%');
        } else {
            showModalWithoutProgress();
        }
        handleFormSubmit(e);
    });

    // Функция для показа модального окна после сохранения измененного портфолио
    function showModalWithoutProgress() {
        if (!modalContainer) return;

        const modal = new Modal(modalContainer);

        // Скрываем прогресс-бар
        const progressDiv = modalContainer.querySelector('.progress');
        if (progressDiv) {
            progressDiv.style.display = 'none';
        }

        // Обновляем заголовок
        const title = modalContainer.querySelector('.modal-title');
        if (title) {
            title.textContent = 'Сохранение изменений...';
        }

        // Показываем простое сообщение
        const message = modalContainer.querySelector('.modal-message');
        if (message) {
            message.innerHTML = `
            <div class="text-center py-3">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mb-0">Сохранение изменений в портфолио</p>
            </div>
        `;
        }

        modal.show();
    }

    /**
     * Отображение превью выбранных файлов
     */
    function showFilePreview(fileList) {
        let previewContainer = document.querySelector('.files-preview-container');

        if (!previewContainer) {
            previewContainer = document.createElement('div');
            previewContainer.className = 'files-preview-container mt-3';
            files.parentNode.appendChild(previewContainer);
        }

        previewContainer.innerHTML = `
            <p class="text-muted">Выбрано файлов: ${fileList.length}</p>
            <div class="files-preview-grid"></div>
        `;

        const previewGrid = previewContainer.querySelector('.files-preview-grid');
        Object.assign(previewGrid.style, {
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
            gap: '10px',
            marginTop: '10px'
        });

        const maxPreview = Math.min(fileList.length, 10);

        for (let i = 0; i < maxPreview; i++) {
            const file = fileList[i];
            if (file.type.startsWith('image/')) {
                createImagePreview(file, previewGrid);
            }
        }

        if (fileList.length > maxPreview) {
            const moreText = document.createElement('p');
            moreText.className = 'text-muted mt-2';
            moreText.textContent = `... и еще ${fileList.length - maxPreview} файлов`;
            previewContainer.appendChild(moreText);
        }
    }

    /**
     * Создание превью одного изображения
     */
    function createImagePreview(file, container) {
        const previewItem = document.createElement('div');
        previewItem.className = 'file-preview-item';
        Object.assign(previewItem.style, {
            position: 'relative',
            aspectRatio: '1'
        });

        const objectURL = URL.createObjectURL(file);
        const img = document.createElement('img');

        Object.assign(img, {
            src: objectURL,
            className: 'img-thumbnail',
            title: file.name
        });

        Object.assign(img.style, {
            width: '100%',
            height: '100%',
            objectFit: 'cover'
        });

        img.onload = () => URL.revokeObjectURL(objectURL);
        previewItem.appendChild(img);
        container.appendChild(previewItem);
    }

    /**
     * Показ модального окна с прогрессом
     */
    function showModal(percent) {
        if (!modalContainer) return;

        const bar = modalContainer.querySelector('.progress-bar');
        if (bar) {
            bar.textContent = percent;
        }

        const modal = new Modal(modalContainer);
        modal.show();
    }

    /**
     * Обработка отправки формы через AJAX
     */
    function handleFormSubmit(e) {
        e.preventDefault();
        const data = new FormData(e.target);
        const xhr = new XMLHttpRequest();

        xhr.addEventListener('load', () => {
            handleUploadComplete(xhr);
        });

        xhr.addEventListener('error', (e) => {
            console.error('Ошибка XHR:', e);
            showError('Ошибка сохранения');
        });

        // Для режима редактирования НЕ показываем прогресс
        if (!isEditMode) {
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    updateProgress(e);
                }
            });
        }

        xhr.open(form.method, window.location.href);
        xhr.setRequestHeader('X-REQUESTED-WITH', 'XMLHttpRequest');
        xhr.send(data);
    }

    /**
     * Обновление прогресс-бара
     */
    function updateProgress(e) {
        const progress = (e.loaded / e.total) * 100;
        console.log('Progress:', progress.toFixed(2) + '%');

        if (modalContainer) {
            const bar = modalContainer.querySelector('.progress-bar');
            if (bar) {
                const progressValue = progress.toFixed(2);
                bar.style.width = progressValue + '%';
                bar.setAttribute('aria-valuenow', progressValue);
                bar.textContent = progress.toFixed(0) + '%';
            }
        }
    }

    /**
     * Обработка завершения загрузки
     */
    function handleUploadComplete(xhr) {
        const contentType = xhr.getResponseHeader('Content-Type');

        if (contentType?.indexOf('application/json') !== -1) {
            try {
                const response = JSON.parse(xhr.responseText);

                if (xhr.status >= 200 && xhr.status < 300) {
                    handleSuccessResponse(response);
                } else {
                    handleErrorResponse(response);
                }
            } catch (err) {
                console.error('Ошибка парсинга JSON:', err);
                showError('Ошибка обработки ответа сервера');
            }
        } else if (xhr.status === 0 || xhr.status >= 400) {
            showError('Ошибка соединения с сервером');
        }
    }

    /**
     * Обработка успешного ответа
     */
    function handleSuccessResponse(response) {
        if (response.status === 'success') {
            if (modalContainer) {
                const bar = modalContainer.querySelector('.progress-bar');
                const progressDiv = modalContainer.querySelector('.progress');
                const message = modalContainer.querySelector('.modal-message');
                const footer = modalContainer.querySelector('.modal-footer');
                const title = modalContainer.querySelector('.modal-title');

                if (isEditMode) {
                    // Для редактирования - простое сообщение
                    if (title) {
                        title.innerHTML = '✓ Изменения сохранены!';
                    }

                    if (message) {
                        message.innerHTML = `
                        <div class="alert-success p-3">
                            <p><strong>${response.message || 'Портфолио успешно обновлено!'}</strong></p>
                        </div>
                    `;
                    }
                } else {
                    // Для добавления - с прогресс-баром
                    if (bar) {
                        bar.style.width = '100%';
                        bar.setAttribute('aria-valuenow', '100');
                        bar.textContent = '100%';
                        bar.classList.remove('progress-bar-animated');
                        bar.classList.add('bg-success');
                    }

                    setTimeout(() => {
                        if (progressDiv) {
                            progressDiv.style.display = 'none';
                        }
                    }, 500);

                    if (title) {
                        title.innerHTML = '✓ Загрузка завершена!';
                    }

                    if (message) {
                        message.innerHTML = `
                        <div class="alert-success">
                            <p><strong>${response.message || 'Портфолио успешно загружено!'}</strong></p>
                            <p class="mb-0">Что делать дальше?</p>
                        </div>
                    `;
                    }
                }

                // Update footer with action buttons
                if (footer) {
                    footer.innerHTML = `
                    <button type="button" class="btn btn-outline-primary" onclick="window.location.href='/portfolio/edit/${response.portfolio_id}'">
                        Редактировать портфолио
                    </button>
                    <button type="button" class="btn btn-primary" onclick="window.location.href='/portfolio/add/'">
                        Добавить новое
                    </button>
                `;
                }
            }
        }
    }

    /**
     * Обработка ошибки
     */
    function handleErrorResponse(response) {
        if (modalContainer) {
            const message = modalContainer.querySelector('.modal-message');
            if (message) {
                message.innerHTML = `
                    <div class="alert-danger">
                        ${response.message || 'Произошла ошибка при загрузке'}
                    </div>
                `;
            }

            const progressBar = modalContainer.querySelector('.progress');
            if (progressBar) {
                progressBar.style.display = 'none';
            }
        }
        console.error('Ошибка загрузки:', response);
    }

    /**
     * Отображение сообщения об ошибке
     */
    function showError(message) {
        if (modalContainer) {
            const messageEl = modalContainer.querySelector('.modal-message');
            if (messageEl) {
                messageEl.innerHTML = `<div class="alert-danger">${message}</div>`;
            }

            const progressDiv = modalContainer.querySelector('.progress');
            if (progressDiv) {
                progressDiv.style.display = 'none';
            }

            // Обновляем заголовок
            const title = modalContainer.querySelector('.modal-title');
            if (title) {
                title.textContent = isEditMode ? 'Ошибка сохранения' : 'Ошибка загрузки';
            }
        }
    }
});
