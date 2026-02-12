import {createFormData} from './utils/ajax.js';
import {Modal} from "./components/modal.js";

document.addEventListener("DOMContentLoaded", () => {
    const ratingForm = document.querySelector('form[name=rating]');
    if (!ratingForm) return;

    let isProcessing = false; // Флаг для предотвращения множественных запросов

    function sendRatingToServer(form, selectedScore) {
        if (isProcessing) return;
        isProcessing = true;

        const params = createFormData(form);
        const formData = new URLSearchParams(params);
        formData.set('star', selectedScore);

        if (window.ajaxSend) {
            window.ajaxSend(
                form.action,
                formData.toString(),
                'post',
                (data) => {
                    // Успешный ответ (HTTP 200)
                    isProcessing = false;

                    // Обновляем флаг canRate для обычных пользователей
                    if (!data.is_jury) {
                        form.setAttribute('data-user-can-rate', 'false');
                    }
                    form.setAttribute('value', selectedScore);

                    rateRender(data, selectedScore);
                },
                (error, xhr) => {
                    // Обработка ошибок HTTP (403, 400, 500 и т.д.)
                    isProcessing = false;

                    let errorData = {status: 'error', message: 'Ошибка соединения'};

                    // Пытаемся получить ответ сервера
                    try {
                        if (xhr && xhr.responseText) {
                            errorData = JSON.parse(xhr.responseText);
                        }
                    } catch (e) {
                        console.error('Failed to parse error response', e);
                    }

                    // Обрабатываем специфичные ошибки
                    if (errorData.message && errorData.message.includes('уже оценивали')) {
                        // Обновляем состояние клиента
                        form.setAttribute('data-user-can-rate', 'false');

                        // Показываем сообщение пользователю
                        if (window.Alert) {
                            window.Alert.warning(errorData.message, 3000, 'top-center');
                        }
                    } else {
                        handleRateError(errorData);
                    }
                }
            );
        }
    }

    function handleRateError(errorData) {
        let message = 'Произошла ошибка при установке оценки';

        if (errorData.message) {
            message = errorData.message;
        } else if (errorData.status === 403) {
            message = 'У вас нет прав для оценки этой работы';
        } else if (errorData.status === 400) {
            message = 'Неверные данные для оценки';
        }

        if (window.Alert) {
            window.Alert.error(message, 5000, 'top-center');
        } else {
            alert(message);
        }
    }

    function rateRender(data, selectedScore) {
        const isJury = data.is_jury || false;
        const authorName = data.author || 'Автор';

        let message = '';
        if (isJury) {
            message = `<h3>Оценка жюри установлена!</h3><p>
                Автор проекта: <b>"${authorName}"</b><br/>
                Ваша оценка: <b>${selectedScore}.0</b></p>`;
        } else {
            message = `<h3>Рейтинг успешно установлен!</h3><p>
                Автор проекта: <b>"${authorName}"</b><br/>
                Ваша оценка: <b>${selectedScore}.0</b><br/>
                Общий рейтинг: <b>${data.score_avg?.toFixed(1) || '0.0'}</b></p>`;
        }

        if (window.Alert) {
            window.Alert.success(message, 3000, 'top-center');
        } else {
            alert(message.replace(/<[^>]*>/g, ''));
        }

        updateRatingUI(data, selectedScore, isJury);
    }

    function updateRatingUI(data, selectedScore, isJury) {
        // Обновляем значение в форме
        ratingForm.setAttribute('value', selectedScore);

        // Обновляем отображение личной оценки
        updateUserScoreDisplay(selectedScore);

        // Обновляем среднюю оценку
        if (!isJury && data.score_avg) {
            const summaryScore = document.querySelector('.summary-score');
            if (summaryScore) {
                summaryScore.textContent = data.score_avg.toFixed(1);
            }
        }

        // Визуально отмечаем выбранную звезду
        highlightSelectedStar(selectedScore);
    }

    function highlightSelectedStar(score) {
        // Снимаем выделение со всех звезд
        document.querySelectorAll('.rating-form input[name="star"]').forEach(input => {
            input.checked = false;
        });

        // Отмечаем выбранную звезду
        const selectedInput = document.querySelector(`.rating-form input[name="star"][value="${score}"]`);
        if (selectedInput) {
            selectedInput.checked = true;
        }
    }

    function updateUserScoreDisplay(score) {
        let userScoreElement = document.querySelector('.personal-rating-block');
        if (userScoreElement) {
            userScoreElement.innerHTML = `<span class="me-2">Ваша оценка:</span><b>${score}.0</b>`;
        } else {
            const ratingBlock = document.querySelector('.total-rating-block');
            if (ratingBlock) {
                const userScoreDiv = document.createElement('div');
                userScoreDiv.className = 'personal-rating-block d-flex align-items-center mt-2';
                userScoreDiv.innerHTML = `<span class="me-2">Ваша оценка:</span><b>${score}.0</b>`;
                ratingBlock.after(userScoreDiv);
            }
        }
    }

    function showAuthRequiredModal() {
        // Проверяем, не открыто ли уже модальное окно
        if (document.getElementById('authRequiredModal')) {
            return;
        }

        const modalHtml = `
            <div id="authRequiredModal" class="modal fade" data-backdrop="static">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Требуется авторизация</h5>
                            <button type="button" class="btn-close" data-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>Участвовать в оценке могут только зарегистрированные пользователи.</p>
                            <p>Пожалуйста, войдите в систему или зарегистрируйтесь.</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Закрыть</button>
                            <a href="/login/" class="btn btn-primary">Войти</a>
                            <a href="/register/" class="btn btn-outline-primary">Регистрация</a>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = document.getElementById('authRequiredModal');
        const modalInstance = new Modal(modal);

        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });

        modalInstance.show();
    }

    function checkRatingPermissions(selectedScore, form, callback) {
        // Проверяем права через сервер
        const testForm = new FormData(form);
        testForm.set('star', selectedScore);
        testForm.append('test', 'true');

        if (window.ajaxSend) {
            window.ajaxSend(form.action, new URLSearchParams(testForm).toString(), 'post', (data) => {
                if (data.status === 'error') {
                    handleRateError(data);
                    callback(false);
                } else {
                    callback(true);
                }
            }, () => {
                // Ошибка сети - разрешаем попытку отправки
                callback(true);
            });
        } else {
            callback(true);
        }
    }

    function showRatingConfirmationModal(selectedScore, form) {
        // Проверяем, не открыто ли уже модальное окно
        if (document.getElementById('ratingConfirmModal')) {
            return;
        }

        const modalHtml = `
            <div id="ratingConfirmModal" class="modal fade" data-backdrop="static">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Подтверждение оценки</h5>
                            <button type="button" class="btn-close" data-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>Ваша оценка: <strong>${selectedScore}.0</strong></p>
                            <p>Вы уверены, что хотите поставить такую оценку?</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Отмена</button>
                            <button type="button" class="btn btn-primary" id="confirmRating">Подтвердить</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = document.getElementById('ratingConfirmModal');
        const modalInstance = new Modal(modal);

        const confirmBtn = document.getElementById('confirmRating');

        // Убираем предыдущие обработчики
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

        newConfirmBtn.addEventListener('click', () => {
            modalInstance.close();
            // Небольшая задержка для закрытия модального окна
            setTimeout(() => {
                sendRatingToServer(form, selectedScore);
            }, 100);
        });

        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
        });

        modalInstance.show();
    }

    function submitRating(e) {
        e.preventDefault();
        e.stopPropagation();

        const isAuthenticated = ratingForm.getAttribute('data-user-authenticated') === 'true';
        const canRate = ratingForm.getAttribute('data-user-can-rate') === 'true';
        const isJury = ratingForm.getAttribute('data-is-jury') === 'true';
        const currentScore = ratingForm.getAttribute('value');

        // Находим input через label
        const label = e.target.closest('label');
        if (!label) return;

        const inputId = label.getAttribute('for');
        if (!inputId) return;

        const input = document.getElementById(inputId);
        if (!input || input.name !== 'star') return;

        const selectedScore = input.value;

        if (!canRate) {
            if (!isAuthenticated) {
                // Не авторизован
                if (window.Alert) {
                    window.Alert.warning('Участвовать в оценке могут только зарегистрированные пользователи', 3000, 'top-center');
                } else {
                    showAuthRequiredModal();
                }
            } else if (currentScore && !isJury) {
                // Уже голосовал (обычный пользователь)
                const message = `Вы уже оценили эту работу. Ваша оценка: ${currentScore}.0`;
                if (window.Alert) window.Alert.warning(message, 3000, 'top-center');
            } else if (isJury) {
                // Жюри после дедлайна
                const message = ratingForm.classList.contains('show-rating')
                    ? 'Голосование жюри завершено'
                    : 'Срок голосования истек';
                if (window.Alert) window.Alert.warning(message, 3000, 'top-center');
            }

            return false;
        }

        // Если пользователь может голосовать - продолжаем
        // Для оценок 1-3 показываем подтверждение
        if (parseInt(selectedScore) <= 3) {
            checkRatingPermissions(selectedScore, ratingForm, (hasPermission) => {
                if (hasPermission) {
                    showRatingConfirmationModal(selectedScore, ratingForm);
                }
            });
        } else {
            // Для высоких оценок отправляем сразу
            sendRatingToServer(ratingForm, selectedScore);
        }

        return false;
    }

    // Удаляем старый обработчик и добавляем новый
    ratingForm.removeEventListener("click", submitRating);
    ratingForm.addEventListener("click", submitRating);

    // Также предотвращаем стандартную отправку формы
    ratingForm.addEventListener("submit", (e) => {
        e.preventDefault();
        return false;
    });
});
