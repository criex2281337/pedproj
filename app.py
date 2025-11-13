from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import bcrypt
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Главная страница
@app.route('/')
def index():
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
        native_language = request.form.get('native_language', 'Russian')
        target_language = request.form.get('target_language', 'English')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            flash('Username or email already exists')
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
        flash('Registration successful!')
        return redirect(url_for('dashboard'))
    
    return render_template('auth/register.html')

# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
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
            
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
        
        conn.close()
    
    return render_template('auth/login.html')

# Выход
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Дашборд
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
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
    
    return render_template('lessons/list.html', 
                         lessons=lessons, 
                         user=user,
                         completed_lessons=completed_lessons)

# Практика урока
@app.route('/lesson/<int:lesson_id>')
def lesson_practice(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,))
    lesson = cursor.fetchone()
    
    if not lesson:
        flash('Lesson not found')
        return redirect(url_for('lessons_list'))
    
    cursor.execute('''
        SELECT * FROM exercises 
        WHERE lesson_id = ? 
        ORDER BY order_index
    ''', (lesson_id,))
    exercises = cursor.fetchall()
    
    # Преобразуем options из JSON в список
    formatted_exercises = []
    for ex in exercises:
        exercise_dict = dict(ex)
        if ex['options']:
            try:
                exercise_dict['options'] = json.loads(ex['options'])
            except:
                exercise_dict['options'] = []
        else:
            exercise_dict['options'] = []
        formatted_exercises.append(exercise_dict)
    
    conn.close()
    
    return render_template('lessons/practice.html', 
                         lesson=lesson, 
                         exercises=formatted_exercises)

# Проверка ответов
@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    user_answer = data.get('user_answer', '')
    
    if not exercise_id:
        return jsonify({'error': 'Exercise ID is required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM exercises WHERE id = ?', (exercise_id,))
    exercise = cursor.fetchone()
    
    if not exercise:
        return jsonify({'error': 'Exercise not found'}), 404
    
    is_correct = user_answer.strip().lower() == exercise['correct_answer'].strip().lower()
    
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
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    score = data.get('score', 0)
    
    if not lesson_id:
        return jsonify({'error': 'Lesson ID is required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем награду за урок
    cursor.execute('SELECT xp_reward FROM lessons WHERE id = ?', (lesson_id,))
    lesson = cursor.fetchone()
    if not lesson:
        return jsonify({'error': 'Lesson not found'}), 404
        
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
    else:
        # Создаем новый прогресс
        cursor.execute('''
            INSERT INTO user_progress (user_id, lesson_id, completed, score, completed_at, attempts)
            VALUES (?, ?, TRUE, ?, datetime('now'), 1)
        ''', (session['user_id'], lesson_id, score))
    
    # Обновляем XP пользователя
    cursor.execute('''
        UPDATE users SET xp = xp + ? WHERE id = ?
    ''', (xp_reward, session['user_id']))
    
    conn.commit()
    
    # Получаем обновленные данные пользователя
    cursor.execute('SELECT xp FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    conn.close()
    
    # Обновляем XP в сессии
    session['xp'] = user['xp']
    
    return jsonify({
        'success': True,
        'xp_earned': xp_reward,
        'total_xp': user['xp']
    })

# Профиль пользователя
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    # Статистика
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
    
    conn.close()
    
    return render_template('profile.html', 
                         user=user, 
                         stats=stats,
                         exercises_stats=exercises_stats,
                         correct_stats=correct_stats)

if __name__ == '__main__':
    if not os.path.exists('database.db'):
        print("Please run init_db.py first to initialize the database")
    else:
        app.run(debug=True, host='0.0.0.0', port=5000)