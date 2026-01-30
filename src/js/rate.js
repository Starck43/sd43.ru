import {createFormData} from './utils/ajax.js';
import {Modal} from "./components/modal.js";

document.addEventListener("DOMContentLoaded", () => {
    const ratingForm = document.querySelector('form[name=rating]');
    if (!ratingForm) return;

    function sendRatingToServer(form, selectedScore) {
        const params = createFormData(form);
        if (window.ajaxSend) {
            window.ajaxSend(form.action, params, 'post', (data) => {
                if (data.status === 'error') {
                    handleRateError(data);
                } else {
                    rateRender(data, selectedScore);
                }
            });
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
                Общий рейтинг: <b>${data.score_avg.toFixed(1)}</b></p>`;
        }

        if (window.Alert) {
            window.Alert.success(message, 3000, 'top-center');
        } else {
            alert(message.replace(/<[^>]*>/g, ''));
        }

        updateRatingUI(data, selectedScore, isJury);
    }

    function updateRatingUI(data, selectedScore, isJury) {
        ratingForm.setAttribute('value', selectedScore);

        updateUserScoreDisplay(selectedScore);

        if (!isJury && data.score_avg) {
            const summaryScore = document.querySelector('.summary-score');
            if (summaryScore) {
                summaryScore.textContent = data.score_avg.toFixed(1);
            }
        }
    }

    function updateUserScoreDisplay(score) {
        let userScoreElement = document.querySelector('.personal-rating-block');
        if (userScoreElement) {
            userScoreElement.innerHTML = `<span style="color: green">Ваша новая оценка:</span><b>${score}.0</b>`;
        } else {
            const ratingBlock = document.querySelector('.total-rating-block');
            if (ratingBlock) {
                const userScoreDiv = document.createElement('div');
                userScoreDiv.className = 'personal-rating-block d-flex';
                userScoreDiv.innerHTML = `<span>Ваша текущая оценка:</span><b>${score}.0</b>`;
                ratingBlock.after(userScoreDiv);
            }
        }
    }

    function showAuthRequiredModal() {
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
        let modalInstance;

        if (window.modalInstances && window.modalInstances.has('#authRequiredModal')) {
            modalInstance = window.modalInstances.get('#authRequiredModal');
        } else {
            modalInstance = new Modal(modal);
            if (window.modalInstances) {
                window.modalInstances.set('#authRequiredModal', modalInstance);
            }
        }

        modal.addEventListener('modal:hidden', () => {
            modal.remove();
            if (window.modalInstances) {
                window.modalInstances.delete('#authRequiredModal');
            }
        });

        modalInstance.show();
    }

    function submitRating(e) {
        const isAuthenticated = ratingForm.getAttribute('data-user-authenticated') === 'true';
        const canRate = ratingForm.getAttribute('data-user-can-rate') === 'true';
        const isJury = ratingForm.getAttribute('data-is-jury') === 'true';
        const currentScore = ratingForm.getAttribute('value');

        if (!canRate) {
            e.preventDefault();

            if (!isAuthenticated) {
                // Не авторизован - показать модальное окно входа
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
                    : 'Срок голосования жюри истек';
                if (window.Alert) window.Alert.warning(message, 3000, 'top-center');
            }
            return;
        }

        if (e.target.localName === 'input') {
            const selectedScore = e.target.value;

            // Сначала проверяем права голосования через сервер
            // Для низких оценок показываем подтверждение только после успешной проверки прав.
            // Создаем временную форму для проверки прав
            const testForm = new FormData();
            testForm.append('portfolio', ratingForm.querySelector('input[name="portfolio"]').value);
            testForm.append('star', selectedScore);
            testForm.append('csrfmiddlewaretoken', ratingForm.querySelector('input[name="csrfmiddlewaretoken"]').value);

            // Добавляем параметр test=true для проверки прав без сохранения
            testForm.append('test', 'true');

            // Отправляем тестовый запрос для проверки прав
            if (window.ajaxSend) {
                window.ajaxSend(ratingForm.action, new URLSearchParams(testForm).toString(), 'post', (data) => {
                    if (data.status === 'error') {
                        handleRateError(data);
                    } else {
                        // Если права есть - показываем подтверждение для низкой оценки
                        showRatingConfirmationModal(selectedScore, ratingForm);
                    }
                });
            }
        }
    }

    function showRatingConfirmationModal(selectedScore, form) {
        const modalHtml = `
            <div id="ratingConfirmModal" class="modal fade" data-backdrop="static">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Подтверждение рейтинга</h5>
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
        let modalInstance;

        if (window.modalInstances && window.modalInstances.has('#ratingConfirmModal')) {
            modalInstance = window.modalInstances.get('#ratingConfirmModal');
        } else {
            modalInstance = new Modal(modal);
            if (window.modalInstances) {
                window.modalInstances.set('#ratingConfirmModal', modalInstance);
            }
        }

        document.getElementById('confirmRating').addEventListener('click', () => {
            modalInstance.close();
            sendRatingToServer(form, selectedScore);
        });

        modal.addEventListener('modal:hidden', () => {
            modal.remove();
            if (window.modalInstances) {
                window.modalInstances.delete('#ratingConfirmModal');
            }
        });

        modalInstance.show();
    }

    ratingForm.addEventListener("click", submitRating);
});
