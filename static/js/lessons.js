// Функции для работы с уроками
class LessonManager {
    constructor() {
        this.currentExercise = 0;
        this.exercises = [];
        this.score = 0;
        this.userAnswers = [];
        console.log('LessonManager initialized');
        this.init();
    }
    
    init() {
        console.log('Starting initialization...');
        this.loadExercises();
        this.setupEventListeners();
        this.showExercise(0);
    }
    
    loadExercises() {
        const exerciseElements = document.querySelectorAll('.exercise');
        console.log('Found exercises:', exerciseElements.length);
        
        this.exercises = Array.from(exerciseElements).map((el, index) => {
            const options = JSON.parse(el.dataset.options || '[]');
            console.log(`Exercise ${index}:`, {
                id: el.dataset.id,
                question: el.querySelector('.exercise-question').textContent,
                correctAnswer: el.dataset.correctAnswer,
                options: options
            });
            
            return {
                id: el.dataset.id,
                type: el.dataset.type,
                question: el.querySelector('.exercise-question').textContent,
                correctAnswer: el.dataset.correctAnswer,
                options: options,
                explanation: el.dataset.explanation
            };
        });
    }
    
    setupEventListeners() {
        console.log('Setting up event listeners...');
        
        // Кнопка проверки ответа
        const checkBtn = document.getElementById('checkAnswer');
        if (checkBtn) {
            console.log('Check button found');
            checkBtn.addEventListener('click', () => {
                console.log('Check button clicked');
                this.checkAnswer();
            });
        } else {
            console.error('Check button not found!');
        }
        
        // Кнопка следующего упражнения
        const nextBtn = document.getElementById('nextExercise');
        if (nextBtn) {
            console.log('Next button found');
            nextBtn.addEventListener('click', () => {
                console.log('Next button clicked');
                this.nextExercise();
            });
        }
        
        // Выбор вариантов ответа
        const optionButtons = document.querySelectorAll('.option-btn');
        console.log('Option buttons found:', optionButtons.length);
        
        optionButtons.forEach((btn, index) => {
            btn.addEventListener('click', (e) => {
                console.log('Option clicked:', e.target.textContent);
                this.selectOption(e.target);
            });
            
            // Добавляем стиль для визуальной обратной связи
            btn.style.cursor = 'pointer';
            btn.style.transition = 'all 0.2s ease';
        });
        
        // Enter для проверки ответа
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                console.log('Enter pressed');
                const nextBtn = document.getElementById('nextExercise');
                const checkBtn = document.getElementById('checkAnswer');
                
                if (nextBtn && nextBtn.style.display !== 'none') {
                    this.nextExercise();
                } else if (checkBtn && checkBtn.style.display !== 'none') {
                    this.checkAnswer();
                }
            }
        });
        
        console.log('Event listeners setup complete');
    }
    
    showExercise(index) {
        console.log('Showing exercise:', index);
        
        // Скрываем все упражнения
        document.querySelectorAll('.exercise').forEach(el => {
            el.style.display = 'none';
        });
        
        // Показываем текущее упражнение
        const currentExercise = document.querySelector(`.exercise[data-index="${index}"]`);
        if (currentExercise) {
            currentExercise.style.display = 'block';
            console.log('Exercise displayed');
        } else {
            console.error('Exercise not found for index:', index);
        }
        
        // Обновляем прогресс
        this.updateProgressBar();
        
        // Сбрасываем состояние
        this.resetExerciseState();
    }
    
    resetExerciseState() {
        console.log('Resetting exercise state');
        
        // Сбрасываем выбранные варианты
        const optionButtons = document.querySelectorAll('.option-btn');
        optionButtons.forEach(btn => {
            btn.classList.remove('selected');
            btn.style.borderColor = '';
            btn.style.background = '';
            btn.style.color = '';
            btn.style.pointerEvents = 'auto';
        });
        
        // Скрываем фидбэк
        const feedback = document.querySelector('.feedback');
        if (feedback) {
            feedback.style.display = 'none';
        }
        
        // Показываем/скрываем кнопки
        this.updateButtonStates();
    }
    
    updateProgressBar() {
        const progress = ((this.currentExercise) / this.exercises.length) * 100;
        const progressFill = document.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        
        const progressText = document.querySelector('.exercise-counter .progress-text');
        if (progressText) {
            progressText.textContent = `${this.currentExercise + 1}`;
        }
        
        console.log('Progress updated:', progress + '%');
    }
    
    updateButtonStates() {
        const checkBtn = document.getElementById('checkAnswer');
        const nextBtn = document.getElementById('nextExercise');
        
        if (checkBtn) {
            checkBtn.style.display = 'block';
            checkBtn.disabled = false;
        }
        if (nextBtn) {
            nextBtn.style.display = 'none';
        }
        
        console.log('Button states updated');
    }
    
    selectOption(button) {
        console.log('Selecting option:', button.textContent);
        
        // Сбрасываем выбор
        document.querySelectorAll('.option-btn').forEach(btn => {
            btn.classList.remove('selected');
            btn.style.borderColor = '';
            btn.style.background = '';
            btn.style.color = '';
        });
        
        // Выбираем текущую кнопку
        button.classList.add('selected');
        button.style.borderColor = 'var(--primary-color)';
        button.style.background = 'var(--primary-color)';
        button.style.color = 'white';
        
        console.log('Option selected successfully');
    }
    
    async checkAnswer() {
        console.log('Checking answer...');
        
        const currentEx = this.exercises[this.currentExercise];
        const selected = document.querySelector('.option-btn.selected');
        
        if (!selected) {
            console.log('No option selected');
            this.showNotification('Пожалуйста, выберите ответ', 'error');
            return;
        }
        
        const userAnswer = selected.textContent;
        console.log('User answer:', userAnswer, 'Correct answer:', currentEx.correctAnswer);
        
        try {
            const response = await fetch('/check_answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    exercise_id: currentEx.id,
                    user_answer: userAnswer
                })
            });
            
            const result = await response.json();
            console.log('Server response:', result);
            
            if (result.error) {
                this.showNotification(result.error, 'error');
                return;
            }
            
            // Показываем правильный ответ и объяснение
            this.showFeedback(result.is_correct, result.correct_answer, result.explanation);
            
            // Сохраняем результат
            this.userAnswers.push({
                exerciseId: currentEx.id,
                userAnswer: userAnswer,
                isCorrect: result.is_correct
            });
            
            if (result.is_correct) {
                this.score++;
            }
            
        } catch (error) {
            console.error('Error checking answer:', error);
            this.showNotification('Ошибка при проверке ответа', 'error');
        }
    }
    
    showFeedback(isCorrect, correctAnswer, explanation) {
        console.log('Showing feedback:', { isCorrect, correctAnswer, explanation });
        
        const feedback = document.querySelector('.feedback');
        const checkBtn = document.getElementById('checkAnswer');
        const nextBtn = document.getElementById('nextExercise');
        
        if (feedback) {
            feedback.className = `feedback ${isCorrect ? 'correct' : 'incorrect'}`;
            feedback.innerHTML = `
                <strong>${isCorrect ? 'Правильно! 🎉' : 'Неправильно 😞'}</strong>
                ${!isCorrect ? `<div style="margin-top: 10px;">Правильный ответ: <strong>${correctAnswer}</strong></div>` : ''}
                ${explanation ? `<div class="explanation">💡 ${explanation}</div>` : ''}
            `;
            feedback.style.display = 'block';
        }
        
        // Подсвечиваем правильный и неправильный ответы
        document.querySelectorAll('.option-btn').forEach(btn => {
            btn.style.pointerEvents = 'none'; // Блокируем дальнейшие клики
            
            if (btn.textContent === correctAnswer) {
                // Правильный ответ - зеленый
                btn.style.borderColor = '#28a745';
                btn.style.background = '#d4edda';
                btn.style.color = '#155724';
            } else if (btn.classList.contains('selected') && !isCorrect) {
                // Неправильно выбранный ответ - красный
                btn.style.borderColor = '#dc3545';
                btn.style.background = '#f8d7da';
                btn.style.color = '#721c24';
            }
        });
        
        if (checkBtn) {
            checkBtn.style.display = 'none';
            checkBtn.disabled = true;
        }
        if (nextBtn) {
            nextBtn.style.display = 'block';
        }
        
        console.log('Feedback displayed');
    }
    
    nextExercise() {
        console.log('Moving to next exercise');
        this.currentExercise++;
        
        if (this.currentExercise < this.exercises.length) {
            this.showExercise(this.currentExercise);
        } else {
            this.completeLesson();
        }
    }
    
    async completeLesson() {
        console.log('Completing lesson');
        const lessonId = document.querySelector('.lesson-container').dataset.lessonId;
        const accuracy = Math.round((this.score / this.exercises.length) * 100);
        
        try {
            const response = await fetch('/complete_lesson', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    lesson_id: lessonId,
                    score: accuracy
                })
            });
            
            const result = await response.json();
            console.log('Lesson completion result:', result);
            
            if (result.error) {
                this.showNotification(result.error, 'error');
                return;
            }
            
            // Показываем экран результатов
            this.showResults(accuracy, result.xp_earned, result.total_xp);
            
        } catch (error) {
            console.error('Error completing lesson:', error);
            this.showResults(accuracy, 10, 0);
        }
    }
    
    showResults(accuracy, xpEarned, totalXp) {
        console.log('Showing results:', { accuracy, xpEarned, totalXp });
        
        const lessonContainer = document.querySelector('.lesson-container');
        lessonContainer.innerHTML = `
            <div class="results-container">
                <div class="results-card" style="text-align: center; padding: 3rem; background: white; border-radius: 16px; box-shadow: 0 8px 25px rgba(0,0,0,0.1);">
                    <h2 style="color: var(--primary-color); margin-bottom: 2rem;">Урок завершен! 🎉</h2>
                    <div class="results-stats" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 2rem; margin-bottom: 3rem;">
                        <div class="stat">
                            <div class="stat-value" style="font-size: 2.5rem; color: var(--primary-color); font-weight: bold;">${accuracy}%</div>
                            <div class="stat-label" style="color: var(--text-light);">Точность</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="font-size: 2.5rem; color: var(--primary-color); font-weight: bold;">${xpEarned}</div>
                            <div class="stat-label" style="color: var(--text-light);">XP получено</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value" style="font-size: 2.5rem; color: var(--primary-color); font-weight: bold;">${totalXp}</div>
                            <div class="stat-label" style="color: var(--text-light);">Всего XP</div>
                        </div>
                    </div>
                    <div class="results-actions" style="display: flex; gap: 1rem; justify-content: center;">
                        <a href="/lessons" class="btn btn-outline">К списку уроков</a>
                        <a href="/dashboard" class="btn btn-primary">Продолжить обучение</a>
                    </div>
                </div>
            </div>
        `;
    }
    
    showNotification(message, type = 'info') {
        // Создаем красивое уведомление
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        if (type === 'error') {
            notification.style.background = '#dc3545';
        } else {
            notification.style.background = 'var(--primary-color)';
        }
        
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Удаляем через 3 секунды
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Добавляем CSS для анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .option-btn {
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .option-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
`;
document.head.appendChild(style);

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing LessonManager...');
    
    if (document.querySelector('.lesson-container')) {
        console.log('Lesson container found, starting...');
        window.lessonManager = new LessonManager();
    } else {
        console.error('Lesson container not found!');
    }
});
