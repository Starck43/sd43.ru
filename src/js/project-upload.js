import {Modal} from './components/modal.js';

document.addEventListener("DOMContentLoaded", () => {
    const modalContainer = document.getElementById('progressModal');
    const form = document.querySelector('#uploadProjectForm');
    const isEditMode = window.location.pathname.includes('/edit/');

    if (!form) return;

    const exhibition = form.querySelector('select[name=exhibition]');
    const owner = form.querySelector('select[name=owner]');
    const nominations = form.querySelector('select[name=nominations]');
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
    };

    // Инициализация видимости полей
    function initFieldVisibility() {
        if (!exhibition) return;

        if (exhibition.value === "") {
            attributes?.classList.add('hidden');
            if (owner) owner.closest('.form-group')?.classList.remove('hidden');
        } else {
            nominationsField?.classList.remove('hidden');
            if (owner) owner.closest('.form-group')?.classList.add('hidden');
        }
    }

    // Загрузка маппинга номинаций → категории
    let nominationsToCategories = {};

    function loadNominationsCategoriesMapping() {
        return fetch('/api/nominations-categories-mapping/')
            .then(response => response.json())
            .then(data => {
                nominationsToCategories = data || {};
            })
            .catch(error => {
                console.error('Error loading nominations mapping:', error);
            });
    }

    // Автоматический выбор категорий по номинациям
    function updateCategoriesFromNominations() {
        if (!categoriesField) return;

        const selectedNominations = Array.from(nominations?.selectedOptions || []).map(opt => opt.value);
        const selectedCategories = new Set();

        selectedNominations.forEach(nominationId => {
            const categoryId = nominationsToCategories[nominationId];
            if (categoryId && categoryId !== 'None' && categoryId !== 'null') {
                selectedCategories.add(categoryId);
            }
        });

        // Находим все чекбоксы и их контейнеры
        const checkboxes = categoriesField.querySelectorAll('input[type="checkbox"]');

        checkboxes.forEach(checkbox => {
            const checkboxContainer = checkbox.closest('.form-check');
            const shouldBeVisible = selectedCategories.has(checkbox.value);

            if (checkboxContainer) {
                // Показываем/скрываем чекбокс
                checkboxContainer.style.display = shouldBeVisible ? 'block' : 'none';
                checkbox.checked = shouldBeVisible;
                checkbox.disabled = true; // Делаем read-only
            }
        });

        // ПОКАЗЫВАЕМ/СКРЫВАЕМ поле категорий
        if (selectedCategories.size > 0) {
            categoriesField.classList.remove('hidden');
        } else {
            categoriesField.classList.add('hidden');
        }
    }

    // Загрузка выставок по участнику
    function loadExhibitionsByOwner(ownerId) {
        if (!exhibition || !ownerId) return;
        // Если выставка уже выбрана - не перезагружаем
        if (exhibition.value) return;

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


    // Загрузка участников выставки
    function loadExhibitionExhibitors(exhibitionId) {
        if (!owner) return;

        // Сохраняем текущее значение
        const currentOwner = owner.value;

        fetch(`/api/get-exhibitors-by-exhibition/?exhibition_id=${exhibitionId}`)
            .then(response => response.json())
            .then(data => {
                // Сохраняем все options
                const allOptions = Array.from(owner.options);

                // Очищаем select
                owner.innerHTML = '';

                // Добавляем пустой option
                const emptyOption = document.createElement('option');
                emptyOption.value = '';
                emptyOption.textContent = '-- Выберите участника --';
                owner.appendChild(emptyOption);

                // Добавляем участников этой выставки
                if (data.exhibitors && data.exhibitors.length > 0) {
                    data.exhibitors.forEach(exh => {
                        const option = document.createElement('option');
                        option.value = exh.id;
                        option.textContent = exh.name;

                        // Восстанавливаем выбранного участника
                        if (currentOwner === String(exh.id)) {
                            option.selected = true;
                        }

                        owner.appendChild(option);
                    });
                }

                // Показываем поле участника
                owner.closest('.form-group')?.classList.remove('hidden');
            })
            .catch(error => {
                console.error('Error loading exhibitors:', error);
                // Показываем всех участников при ошибке
                Array.from(owner.options).forEach(option => {
                    option.hidden = false;
                });
            });
    }

    // Загрузка номинаций по выставке
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

    // Функция для AJAX поиска участников
    function setupOwnerAutocomplete() {
        if (!owner) return;

        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'form-control';
        searchInput.placeholder = 'Введите название участника ...';
        searchInput.autocomplete = 'off';

        // Создаем новый select
        const newSelect = document.createElement('select');
        newSelect.name = owner.name;
        newSelect.id = owner.id;
        newSelect.className = owner.className;
        newSelect.required = false;

        // Позиционирование
        newSelect.style.cssText = `
            position: absolute;
            display: none;
            width: 100%;
            max-height: 200px;
            margin-top: 0;
            background-color: #f3f3f9;
            overflow-y: auto;
            z-index: 1000;
        `;

        // Заменяем старый select
        const container = owner.parentNode;
        container.replaceChild(newSelect, owner);
        container.insertBefore(searchInput, newSelect);

        let timeoutId;
        let currentExhibitionId = '';
        let lastLoadedExhibitors = [];

        // Получаем ID выставки если выбрана
        const exhibitionSelect = form.querySelector('select[name="exhibition"]');
        if (exhibitionSelect) {
            currentExhibitionId = exhibitionSelect.value;
            exhibitionSelect.addEventListener('change', function () {
                currentExhibitionId = this.value;
                // При смене выставки очищаем кэш
                lastLoadedExhibitors = [];
            });
        }

        // Функция показа/скрытия select
        function showSelect(size = 8) {
            newSelect.style.display = 'block';
            newSelect.size = size;
        }

        function hideSelect() {
            newSelect.style.display = 'none';
            newSelect.size = 0;
        }

        // Функция для загрузки участников
        function loadExhibitors(query = '') {
            clearTimeout(timeoutId);

            // Показываем select при любом вводе (кроме когда уже выбрано значение)
            if (!newSelect.value) {
                showSelect(8);
            }

            // AJAX запрос только для пустого запроса или 3+ символов
            if (query === '' || query.length >= 3) {
                timeoutId = setTimeout(() => {
                    let url = `/api/search-exhibitors/?limit=50`;
                    if (query.length >= 3) {
                        url += `&q=${encodeURIComponent(query)}`;
                    }
                    if (currentExhibitionId) {
                        url += `&exhibition_id=${currentExhibitionId}`;
                    }

                    fetch(url)
                        .then(response => response.json())
                        .then(data => {
                            // Сохраняем для локальной фильтрации
                            if (query === '' || query.length < 3) {
                                lastLoadedExhibitors = data.exhibitors || [];
                            }
                            updateSelectOptions(newSelect, data.exhibitors, query);
                        })
                        .catch(console.error);
                }, query.length >= 3 ? 500 : 100);
            }
            // Локальная фильтрация для 1-2 символов
            else if (query.length > 0 && query.length < 3) {
                if (lastLoadedExhibitors.length > 0) {
                    const filtered = lastLoadedExhibitors.filter(exh =>
                        exh.name.toLowerCase().includes(query.toLowerCase())
                    );
                    updateSelectOptions(newSelect, filtered, query);
                } else {
                    // Если нет кэша - загружаем всех сначала
                    loadExhibitors('');
                }
            }
        }

        // Показ select при фокусе
        searchInput.addEventListener('focus', () => {
            showSelect(8);
            if (!searchInput.value.trim()) {
                loadExhibitors('');
            }
        });

        // Обработка ввода текста
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();

            // Если стираем выбранное значение - сбрасываем select
            if (newSelect.value && query === '') {
                newSelect.value = '';
            }

            // Если поле не пустое или select не имеет значения - показываем
            if (query || !newSelect.value) {
                showSelect(8);
            }

            loadExhibitors(query);
        });

        // Обработка выбора из списка
        newSelect.addEventListener('change', () => {
            if (newSelect.value) {
                const selectedOption = newSelect.options[newSelect.selectedIndex];
                searchInput.value = selectedOption.textContent;
                // Скрываем список после выбора
                setTimeout(() => hideSelect(), 100);
            } else {
                searchInput.value = '';
                showSelect(8);
            }
        });

        // Скрытие select при клике вне
        document.addEventListener('click', (e) => {
            if (!container.contains(e.target)) {
                hideSelect();
            }
        });

        if (isEditMode && owner && owner.value) {
            const currentOwnerOption = owner.querySelector(`option[value="${owner.value}"]`);
            if (currentOwnerOption) {
                searchInput.value = currentOwnerOption.textContent;
                newSelect.value = owner.value;

                // Создаем hidden input если его нет
                let hiddenInput = container.querySelector('input[type="hidden"][name="owner"]');
                if (!hiddenInput) {
                    hiddenInput = document.createElement('input');
                    hiddenInput.type = 'hidden';
                    hiddenInput.name = 'owner';
                    container.appendChild(hiddenInput);
                }
                hiddenInput.value = owner.value;
            }
        }
    }

    // Функция обновления options в select
    function updateSelectOptions(selectElement, exhibitors, query = '') {
        const currentValue = selectElement.value;
        selectElement.innerHTML = '';

        if (exhibitors.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = query ? 'Ничего не найдено' : 'Нет доступных участников';
            option.disabled = true;
            selectElement.appendChild(option);
            return;
        }

        // Добавляем участников
        exhibitors.forEach(exh => {
            const option = document.createElement('option');
            option.value = exh.id;
            option.textContent = exh.name;
            if (String(exh.id) === currentValue) {
                option.selected = true;
            }
            selectElement.appendChild(option);
        });
    }

    // Инициализация всех обработчиков
    function initAllHandlers() {
        // Инициализация видимости
        initFieldVisibility();

        setupOwnerAutocomplete();

        // Если участник уже выбран при загрузке, но выставка не выбрана
        if (owner && owner.value && !exhibition.value) {
            loadExhibitionsByOwner(owner.value);
        }

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
                //categoriesField?.classList.add('hidden');
                attributes?.classList.remove('hidden');
                if (owner) owner.closest('.form-group')?.classList.add('hidden');

                loadNominationsForExhibition(value);
                loadExhibitionExhibitors(value);

            } else {
                nominationsField?.classList.add('hidden');
                categoriesField?.classList.add('hidden');
                attributes?.classList.add('hidden');

                if (owner) {
                    owner.closest('.form-group')?.classList.remove('hidden');
                    // Показываем всех участников
                    Array.from(owner.options).forEach(option => {
                        option.hidden = false;
                    });
                }

                if (nominations) {
                    nominations.innerHTML = '<option value="">-- Сначала выберите выставку --</option>';
                }
            }
        });

        // Обработчик изменения владельца портфолио
        owner?.addEventListener('change', (e) => {
            if (e.target.value) {
                loadExhibitionsByOwner(e.target.value);
            } else {
                if (!exhibition.value) {
                    exhibition.innerHTML = '<option value="">-- Выберите автора проекта --</option>';
                }
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
                        <div class="status-success p-3">
                            <h3><strong>${response.message || 'Портфолио успешно обновлено!'}</strong></h3>
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
                        <div class="status-success">
                            <h3><strong>${response.message || 'Портфолио успешно загружено!'}</strong></h3>
                        </div>
                    `;
                    }
                }

                // Update footer with action buttons
                if (footer) {
                    footer.innerHTML = `
                    <button type="button" class="btn btn-primary w-100" onclick="window.location.href='/portfolio/edit/${response.portfolio_id}'">
                        Продолжить редактирование
                    </button>
                    <button type="button" class="btn btn-secondary w-100" onclick="window.location.href='/portfolio/add/'">
                        Добавить новое портфолио
                    </button>
                    <button type="button" class="btn btn-secondary w-100" onclick="window.location.href='/account'">
                        Перейти в свой профиль 
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
                    <div class="status-danger">
                        ${response.message || 'Произошла ошибка при загрузке.\nПовторите, или обратитесь к администратору'}
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
                messageEl.innerHTML = `<div class="status-danger">${message}</div>`;
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
