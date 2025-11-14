from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import bcrypt
from datetime import datetime, timedelta
import json
import os
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def log_debug(message):
    """Вывод дебаг сообщений в консоль Flask"""
    print(f"🔍 [DEBUG] {datetime.now().strftime('%H:%M:%S')} - {message}")

# Главная страница
@app.route('/')
def index():
    log_debug("Главная страница запрошена")
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        native_language = request.form.get('native_language', 'Русский')
        target_language = request.form.get('target_language', 'Английский')
        
        log_debug(f"Попытка регистрации: {username}, {email}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            flash('Имя пользователя или email уже существуют')
            log_debug(f"Регистрация провалилась: пользователь существует")
            return render_template('auth/register.html')
        
        # Хешируем пароль
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Создаем пользователя
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, native_language, target_language)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, email, password_hash, native_language, target_language))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        session['user_id'] = user_id
        session['username'] = username
        flash('Регистрация прошла успешно!')
        log_debug(f"Успешная регистрация: {username}, ID: {user_id}")
        return redirect(url_for('dashboard'))
    
    log_debug("Отображение формы регистрации")
    return render_template('auth/register.html')

# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        log_debug(f"Попытка входа: {username}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['xp'] = user['xp']
            
            # Обновляем последний вход и проверяем стрик
            today = datetime.now().date()
            last_login_str = user['last_login']
            
            if last_login_str:
                try:
                    last_login = datetime.strptime(last_login_str, '%Y-%m-%d').date()
                    days_diff = (today - last_login).days
                    if days_diff == 1:
                        new_streak = user['streak'] + 1
                    elif days_diff > 1:
                        new_streak = 1
                    else:
                        new_streak = user['streak']
                except:
                    new_streak = 1
            else:
                new_streak = 1
            
            cursor.execute('''
                UPDATE users SET last_login = ?, streak = ? WHERE id = ?
            ''', (today.isoformat(), new_streak, user['id']))
            conn.commit()
            
            flash('Вход выполнен успешно!')
            log_debug(f"Успешный вход: {username}, streak: {new_streak}")
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль')
            log_debug(f"Неудачный вход: {username}")
        
        conn.close()
    
    log_debug("Отображение формы входа")
    return render_template('auth/login.html')

# Выход
@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    session.clear()
    log_debug(f"Выход пользователя: {username}")
    return redirect(url_for('index'))

# Дашборд
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        log_debug("Попытка доступа к дашборду без авторизации")
        return redirect(url_for('login'))
    
    log_debug(f"Дашборд запрошен пользователем: {session['username']}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем данные пользователя
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    # Получаем прогресс
    cursor.execute('''
        SELECT l.*, up.completed, up.score 
        FROM lessons l 
        LEFT JOIN user_progress up ON l.id = up.lesson_id AND up.user_id = ?
        WHERE l.language_id = 1
        ORDER BY l.order_index
    ''', (session['user_id'],))
    lessons = cursor.fetchall()
    
    # Находим следующий урок
    next_lesson = None
    completed_lessons = 0
    for lesson in lessons:
        if lesson['completed']:
            completed_lessons += 1
        elif next_lesson is None:
            next_lesson = lesson
    
    # Получаем лидерборд
    cursor.execute('''
        SELECT username, xp, streak FROM users 
        ORDER BY xp DESC 
        LIMIT 10
    ''')
    leaderboard = cursor.fetchall()
    
    conn.close()
    
    log_debug(f"Дашборд: {completed_lessons}/{len(lessons)} уроков завершено")
    
    return render_template('dashboard.html', 
                         user=user, 
                         lessons=lessons, 
                         leaderboard=leaderboard,
                         next_lesson=next_lesson,
                         completed_lessons=completed_lessons)

# Список уроков
@app.route('/lessons')
def lessons_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    log_debug(f"Список уроков запрошен: {session['username']}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('''
        SELECT l.*, up.completed, up.score 
        FROM lessons l 
        LEFT JOIN user_progress up ON l.id = up.lesson_id AND up.user_id = ?
        WHERE l.language_id = 1
        ORDER BY l.order_index
    ''', (session['user_id'],))
    lessons = cursor.fetchall()
    
    # Считаем завершенные уроки
    completed_lessons = sum(1 for lesson in lessons if lesson['completed'])
    
    conn.close()
    
    log_debug(f"Уроки: найдено {len(lessons)} уроков, завершено {completed_lessons}")
    
    return render_template('lessons/list.html', 
                         lessons=lessons, 
                         user=user,
                         completed_lessons=completed_lessons)

# Практика урока
@app.route('/lesson/<int:lesson_id>')
def lesson_practice(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    log_debug(f"Начало урока {lesson_id} пользователем: {session['username']}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,))
    lesson = cursor.fetchone()
    
    if not lesson:
        flash('Урок не найден')
        log_debug(f"Урок {lesson_id} не найден")
        return redirect(url_for('lessons_list'))
    
    cursor.execute('''
        SELECT * FROM exercises 
        WHERE lesson_id = ? 
        ORDER BY order_index
    ''', (lesson_id,))
    exercises = cursor.fetchall()
    
    # Разделяем упражнения на обучение и практику
    learning_exercises = []
    practice_exercises = []
    
    for ex in exercises:
        exercise_dict = dict(ex)
        if ex['options']:
            try:
                options = json.loads(ex['options'])
                # Перемешиваем варианты ответов для практических упражнений
                if ex['type'] == 'practice':
                    correct_answer = exercise_dict['correct_answer']
                    # Создаем копию и перемешиваем, но запоминаем правильный ответ
                    shuffled_options = options.copy()
                    random.shuffle(shuffled_options)
                    exercise_dict['options'] = shuffled_options
                    exercise_dict['correct_answer'] = correct_answer  # Сохраняем правильный ответ
                else:
                    exercise_dict['options'] = options
            except:
                exercise_dict['options'] = []
        else:
            exercise_dict['options'] = []
        
        if ex['type'] == 'learning':
            learning_exercises.append(exercise_dict)
        else:
            practice_exercises.append(exercise_dict)
    
    conn.close()
    
    # Логируем информацию об упражнениях
    log_debug(f"Урок {lesson_id}: {len(learning_exercises)} обучающих, {len(practice_exercises)} практических упражнений")
    
    return render_template('lessons/practice.html', 
                         lesson=lesson, 
                         learning_exercises=learning_exercises,
                         practice_exercises=practice_exercises)

# Проверка ответов
@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'user_id' not in session:
        log_debug("Попытка проверки ответа без авторизации")
        return jsonify({'error': 'Не авторизован'}), 401
    
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_answer = data.get('user_answer', '')
    
    log_debug(f"Проверка ответа: exercise_id={exercise_id}, user_answer='{user_answer}', user={session['username']}")
    
    if not exercise_id:
        log_debug("Ошибка: exercise_id отсутствует")
        return jsonify({'error': 'ID упражнения обязателен'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM exercises WHERE id = ?', (exercise_id,))
    exercise = cursor.fetchone()
    
    if not exercise:
        log_debug(f"Ошибка: упражнение {exercise_id} не найдено")
        return jsonify({'error': 'Упражнение не найдено'}), 404
    
    # Для упражнений типа multiple_choice сравниваем текст
    is_correct = user_answer.strip() == exercise['correct_answer'].strip()
    
    log_debug(f"Результат проверки: {'ПРАВИЛЬНО' if is_correct else 'НЕПРАВИЛЬНО'}, правильный ответ: '{exercise['correct_answer']}'")
    
    # Сохраняем ответ пользователя
    cursor.execute('''
        INSERT INTO user_answers (user_id, exercise_id, user_answer, is_correct)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], exercise_id, user_answer, is_correct))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'is_correct': is_correct,
        'correct_answer': exercise['correct_answer'],
        'explanation': exercise['explanation'] or ''
    })

# Завершение урока
@app.route('/complete_lesson', methods=['POST'])
def complete_lesson():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    score = data.get('score', 0)
    
    log_debug(f"Завершение урока: lesson_id={lesson_id}, score={score}, user={session['username']}")
    
    if not lesson_id:
        return jsonify({'error': 'ID урока обязателен'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем награду за урок
    cursor.execute('SELECT xp_reward FROM lessons WHERE id = ?', (lesson_id,))
    lesson = cursor.fetchone()
    if not lesson:
        log_debug(f"Ошибка: урок {lesson_id} не найден")
        return jsonify({'error': 'Урок не найден'}), 404
        
    xp_reward = lesson['xp_reward']
    
    # Проверяем, существует ли уже прогресс
    cursor.execute('SELECT * FROM user_progress WHERE user_id = ? AND lesson_id = ?', 
                  (session['user_id'], lesson_id))
    existing_progress = cursor.fetchone()
    
    if existing_progress:
        # Обновляем существующий прогресс
        cursor.execute('''
            UPDATE user_progress 
            SET completed = TRUE, score = ?, completed_at = datetime('now'), attempts = attempts + 1
            WHERE user_id = ? AND lesson_id = ?
        ''', (score, session['user_id'], lesson_id))
        log_debug(f"Обновлен существующий прогресс урока {lesson_id}")
    else:
        cursor.execute('''
            INSERT INTO user_progress (user_id, lesson_id, completed, score, completed_at, attempts)
            VALUES (?, ?, TRUE, ?, datetime('now'), 1)
        ''', (session['user_id'], lesson_id, score))
        log_debug(f"Создан новый прогресс урока {lesson_id}")
    
    cursor.execute('''
        UPDATE users SET xp = xp + ? WHERE id = ?
    ''', (xp_reward, session['user_id']))
    
    conn.commit()
    
    cursor.execute('SELECT xp FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    conn.close()
    
    session['xp'] = user['xp']
    
    log_debug(f"Урок завершен: +{xp_reward} XP, всего XP: {user['xp']}")
    
    return jsonify({
        'success': True,
        'xp_earned': xp_reward,
        'total_xp': user['xp']
    })

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    log_debug(f"Профиль запрошен: {session['username']}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('login'))
    
    cursor.execute('''
        SELECT COUNT(*) as lessons_completed 
        FROM user_progress 
        WHERE user_id = ? AND completed = TRUE
    ''', (session['user_id'],))
    stats = cursor.fetchone()
    
    cursor.execute('''
        SELECT COUNT(*) as exercises_completed 
        FROM user_answers 
        WHERE user_id = ?
    ''', (session['user_id'],))
    exercises_stats = cursor.fetchone()
    
    cursor.execute('''
        SELECT COUNT(*) as correct_answers 
        FROM user_answers 
        WHERE user_id = ? AND is_correct = TRUE
    ''', (session['user_id'],))
    correct_stats = cursor.fetchone()
    
    cursor.execute('''
        SELECT l.title, up.score, up.completed_at 
        FROM user_progress up 
        JOIN lessons l ON up.lesson_id = l.id 
        WHERE up.user_id = ? AND up.completed = TRUE 
        ORDER BY up.completed_at DESC 
        LIMIT 5
    ''', (session['user_id'],))
    recent_lessons = cursor.fetchall()
    
    cursor.execute('''
        SELECT l.title, up.score, up.completed_at
        FROM user_progress up
        JOIN lessons l ON up.lesson_id = l.id
        WHERE up.user_id = ? AND up.completed = TRUE
        ORDER BY up.completed_at DESC
    ''', (session['user_id'],))
    all_completed_lessons = cursor.fetchall()
    
    conn.close()
    
    log_debug(f"Статистика профиля: {stats['lessons_completed']} уроков, {exercises_stats['exercises_completed']} упражнений")
    
    return render_template('profile.html', 
                         user=user, 
                         stats=stats,
                         exercises_stats=exercises_stats,
                         correct_stats=correct_stats,
                         recent_lessons=recent_lessons,
                         all_completed_lessons=all_completed_lessons)

@app.route('/api/user_stats')
def user_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as total_lessons FROM lessons WHERE language_id = 1')
    total_lessons = cursor.fetchone()['total_lessons']
    
    cursor.execute('SELECT COUNT(*) as completed_lessons FROM user_progress WHERE user_id = ? AND completed = TRUE', (session['user_id'],))
    completed_lessons = cursor.fetchone()['completed_lessons']
    
    cursor.execute('SELECT COUNT(*) as total_exercises FROM user_answers WHERE user_id = ?', (session['user_id'],))
    total_exercises = cursor.fetchone()['total_exercises']
    
    cursor.execute('SELECT COUNT(*) as correct_exercises FROM user_answers WHERE user_id = ? AND is_correct = TRUE', (session['user_id'],))
    correct_exercises = cursor.fetchone()['correct_exercises']
    
    cursor.execute('SELECT SUM(xp) as total_xp FROM users WHERE id = ?', (session['user_id'],))
    total_xp = cursor.fetchone()['total_xp'] or 0
    
    cursor.execute('SELECT streak FROM users WHERE id = ?', (session['user_id'],))
    streak = cursor.fetchone()['streak']
    
    conn.close()
    
    accuracy = (correct_exercises / total_exercises * 100) if total_exercises > 0 else 0
    
    return jsonify({
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
        'total_exercises': total_exercises,
        'correct_exercises': correct_exercises,
        'accuracy': round(accuracy, 1),
        'total_xp': total_xp,
        'streak': streak
    })

@app.route('/debug_js')
def debug_js():
    log_debug("Запрос дебаг страницы JavaScript")
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug JavaScript</title>
        <style>
            .option-btn { padding: 20px; margin: 10px; border: 2px solid #ccc; cursor: pointer; }
            .selected { background: green; color: white; }
        </style>
    </head>
    <body>
        <h1>Тест JavaScript</h1>
        <div class="option-btn" onclick="selectOption(this)">Вариант 1</div>
        <div class="option-btn" onclick="selectOption(this)">Вариант 2</div>
        <div class="option-btn" onclick="selectOption(this)">Вариант 3</div>
        <button onclick="checkAnswer()">Проверить ответ</button>
        
        <script>
            function selectOption(btn) {
                // Убираем выделение у всех
                document.querySelectorAll('.option-btn').forEach(b => {
                    b.classList.remove('selected');
                });
                // Выбираем текущую
                btn.classList.add('selected');
                console.log('Выбран:', btn.textContent);
            }
            
            function checkAnswer() {
                const selected = document.querySelector('.option-btn.selected');
                if (!selected) {
                    alert('Выберите вариант!');
                    return;
                }
                alert('Выбран: ' + selected.textContent);
            }
            
            console.log('JavaScript работает!');
        </script>
    </body>
    </html>
    '''

@app.route('/about')
def about():
    log_debug("Страница 'О проекте' запрошена")
    return render_template('about.html')

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    conn = get_db_connection()
    conn.close()
    return render_template('500.html'), 500

@app.route('/health')
def health_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists('database.db'):
        print("Пожалуйста, сначала запустите init_db.py для инициализации базы данных")
    else:
        log_debug("Сервер Flask запускается...")
        app.run(debug=True, host='0.0.0.0', port=5000)
