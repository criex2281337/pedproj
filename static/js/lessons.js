// Простой и надежный скрипт для уроков
console.log('🎯 Lessons script loaded');

let currentExerciseIndex = 0;
let exercises = [];
let correctAnswers = 0;

// Инициализация урока
function initializeLesson() {
    console.log('🔧 Initializing lesson...');
    
    // Находим все упражнения
    exercises = Array.from(document.querySelectorAll('.exercise'));
    console.log('📊 Found exercises:', exercises.length);
    
    // Логируем информацию о каждом упражнении
    exercises.forEach((exercise, index) => {
        console.log(`Exercise ${index}:`, {
            id: exercise.dataset.exerciseId,
            type: exercise.dataset.type,
            index: exercise.dataset.index,
            displayed: exercise.style.display !== 'none'
        });
    });
    
    // Обновляем общее количество упражнений
    const totalExercisesElement = document.getElementById('totalExercises');
    if (totalExercisesElement) {
        totalExercisesElement.textContent = exercises.length;
    }
    
    // Показываем первое упражнение
    showExercise(0);
}

// Показать упражнение по индексу
function showExercise(index) {
    console.log(`🎯 Showing exercise ${index}`);
    
    // Скрываем все упражнения
    exercises.forEach(ex => ex.style.display = 'none');
    
    // Показываем текущее упражнение
    if (exercises[index]) {
        exercises[index].style.display = 'block';
        currentExerciseIndex = index;
        
        // Обновляем UI
        updatePhaseIndicator();
        updateButtons();
        updateProgress();
        
        console.log('✅ Exercise displayed:', exercises[index].dataset.exerciseId);
    } else {
        console.error('❌ Exercise not found for index:', index);
    }
}

// Обновить индикатор фазы
function updatePhaseIndicator() {
    const phaseText = document.getElementById('phaseText');
    const currentExercise = exercises[currentExerciseIndex];
    
    if (currentExercise && currentExercise.dataset.type === 'learning') {
        phaseText.textContent = 'Обучение';
    } else {
        phaseText.textContent = 'Практика';
    }
}

// Обновить кнопки
function updateButtons() {
    const currentExercise = exercises[currentExerciseIndex];
    
    if (currentExercise && currentExercise.dataset.type === 'learning') {
        document.getElementById('nextLearning').style.display = 'block';
        document.getElementById('checkAnswer').style.display = 'none';
        document.getElementById('nextPractice').style.display = 'none';
    } else {
        document.getElementById('nextLearning').style.display = 'none';
        document.getElementById('checkAnswer').style.display = 'block';
        document.getElementById('checkAnswer').textContent = 'Проверить ответ';
        document.getElementById('checkAnswer').disabled = false;
        document.getElementById('nextPractice').style.display = 'none';
    }
}

// Обновить прогресс
function updateProgress() {
    const progress = ((currentExerciseIndex) / exercises.length) * 100;
    const progressFill = document.getElementById('progressFill');
    if (progressFill) {
        progressFill.style.width = `${progress}%`;
    }
    
    const progressText = document.getElementById('currentExercise');
    if (progressText) {
        progressText.textContent = `${currentExerciseIndex + 1}`;
    }
}

// Выбор варианта ответа
function selectOption(button) {
    console.log('🖱️ Click detected on:', button.textContent);
    
    // Убираем выделение у всех кнопок
    const exercise = button.closest('.exercise');
    const allButtons = exercise.querySelectorAll('.option-btn');
    
    allButtons.forEach(btn => {
        btn.classList.remove('selected');
        btn.style.background = '';
        btn.style.color = '';
        btn.style.borderColor = '';
    });
    
    // Выделяем выбранную кнопку
    button.classList.add('selected');
    button.style.background = '#58cc02';
    button.style.color = 'white';
    button.style.borderColor = '#58cc02';
}

// Проверить ответ
async function checkAnswer() {
    console.log('🔍 Checking answer...');
    
    const currentExercise = exercises[currentExerciseIndex];
    if (!currentExercise) {
        alert('❌ Ошибка: текущее упражнение не найдено');
        return;
    }
    
    const exerciseId = currentExercise.dataset.exerciseId;
    const selected = currentExercise.querySelector('.option-btn.selected');
    
    if (!selected) {
        alert('❌ Пожалуйста, выберите ответ!');
        return;
    }
    
    const userAnswer = selected.textContent;
    
    console.log('📤 Sending to server:', { exercise_id: exerciseId, user_answer: userAnswer });
    
    try {
        const checkBtn = document.getElementById('checkAnswer');
        checkBtn.textContent = 'Проверяем...';
        checkBtn.disabled = true;
        
        const response = await fetch('/check_answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                exercise_id: parseInt(exerciseId),
                user_answer: userAnswer
            })
        });
        
        const result = await response.json();
        console.log('📥 Server response:', result);
        
        if (result.error) {
            alert('❌ Ошибка: ' + result.error);
            checkBtn.textContent = 'Проверить ответ';
            checkBtn.disabled = false;
            return;
        }
        
        if (result.is_correct) {
            correctAnswers++;
        }
        
        showResult(currentExercise, result.is_correct, result.correct_answer, result.explanation);
        
    } catch (error) {
        console.error('❌ Network error:', error);
        alert('❌ Ошибка сети');
        const checkBtn = document.getElementById('checkAnswer');
        checkBtn.textContent = 'Проверить ответ';
        checkBtn.disabled = false;
    }
}

// Показать результат
function showResult(exercise, isCorrect, correctAnswer, explanation) {
    console.log('🎯 Showing result:', { isCorrect, correctAnswer });
    
    const allButtons = exercise.querySelectorAll('.option-btn');
    
    // Подсвечиваем ответы
    allButtons.forEach(btn => {
        btn.style.pointerEvents = 'none';
        
        if (btn.textContent === correctAnswer) {
            btn.style.background = '#d4edda';
            btn.style.borderColor = '#28a745';
            btn.style.color = '#155724';
        } else if (btn.classList.contains('selected') && !isCorrect) {
            btn.style.background = '#f8d7da';
            btn.style.borderColor = '#dc3545';
            btn.style.color = '#721c24';
        }
    });
    
    // Показываем фидбэк
    const feedback = exercise.querySelector('.feedback');
    if (feedback) {
        feedback.className = `feedback ${isCorrect ? 'correct' : 'incorrect'}`;
        feedback.innerHTML = `
            <strong>${isCorrect ? '✅ Правильно! 🎉' : '❌ Неправильно 😞'}</strong>
            ${!isCorrect ? `<div style="margin-top: 10px;">Правильный ответ: <strong>${correctAnswer}</strong></div>` : ''}
            ${explanation ? `<div style="margin-top: 10px; font-style: italic;">💡 ${explanation}</div>` : ''}
        `;
        feedback.style.display = 'block';
    }
    
    // Обновляем кнопки
    document.getElementById('checkAnswer').style.display = 'none';
    document.getElementById('nextPractice').style.display = 'block';
}

// Следующее упражнение
function nextExercise() {
    console.log('➡️ Next exercise');
    
    if (currentExerciseIndex < exercises.length - 1) {
        showExercise(currentExerciseIndex + 1);
    } else {
        completeLesson();
    }
}

// Завершить урок
async function completeLesson() {
    console.log('🎉 Lesson completed!');
    
    const lessonId = document.querySelector('.lesson-container').dataset.lessonId;
    const practiceExercises = exercises.filter(ex => ex.dataset.type === 'practice');
    const accuracy = practiceExercises.length > 0 ? 
        Math.round((correctAnswers / practiceExercises.length) * 100) : 100;
    
    try {
        const response = await fetch('/complete_lesson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lesson_id: parseInt(lessonId),
                score: accuracy
            })
        });
        
        const result = await response.json();
        
        if (result.error) {
            alert('❌ Ошибка: ' + result.error);
            return;
        }
        
        showCompletionScreen(accuracy, result.xp_earned, result.total_xp);
        
    } catch (error) {
        console.error('❌ Error:', error);
        showCompletionScreen(accuracy, 10, 0);
    }
}

// Показать экран завершения
function showCompletionScreen(accuracy, xpEarned, totalXp) {
    const lessonContainer = document.querySelector('.lesson-container');
    lessonContainer.innerHTML = `
        <div class="completion-screen">
            <h2 style="color: #58cc02; margin-bottom: 2rem; font-size: 2.5rem;">🎉 Урок завершен!</h2>
            
            <div class="stats-grid">
                <div class="stat">
                    <div class="stat-value">${accuracy}%</div>
                    <div class="stat-label">Точность</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${xpEarned}</div>
                    <div class="stat-label">XP получено</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${totalXp}</div>
                    <div class="stat-label">Всего XP</div>
                </div>
            </div>
            
            <div style="display: flex; gap: 1rem; justify-content: center;">
                <a href="/lessons" class="btn btn-outline" style="padding: 1rem 2rem; text-decoration: none;">📚 К списку уроков</a>
                <a href="/dashboard" class="btn btn-primary" style="padding: 1rem 2rem; text-decoration: none;">🚀 Продолжить обучение</a>
            </div>
        </div>
    `;
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ DOM loaded');
    
    if (document.querySelector('.lesson-container')) {
        console.log('🎯 Lesson page detected');
        initializeLesson();
    }
});
