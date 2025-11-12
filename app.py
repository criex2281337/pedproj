from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'duolingo_secret_123'
app.config['DATABASE'] = 'english_app.db'

def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY,
                  username TEXT UNIQUE,
                  password TEXT,
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  streak INTEGER DEFAULT 0,
                  created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS lessons
                 (id INTEGER PRIMARY KEY,
                  title TEXT,
                  description TEXT,
                  icon TEXT,
                  color TEXT,
                  order_num INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS questions
                 (id INTEGER PRIMARY KEY,
                  lesson_id INTEGER,
                  type TEXT,
                  question TEXT,
                  options TEXT,
                  correct_answer TEXT,
                  xp_reward INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_progress
                 (user_id INTEGER,
                  lesson_id INTEGER,
                  completed BOOLEAN DEFAULT FALSE,
                  score INTEGER DEFAULT 0,
                  completed_at TEXT)''')
    
    # Уроки
    lessons = [
        (1, "Основы 1", "Приветствия и основы", "🟢", "#58cc02", 1),
        (2, "Основы 2", "Простые фразы", "🔵", "#1cb0f6", 2),
        (3, "Еда", "Еда и напитки", "🟡", "#ffcc00", 3),
        (4, "Семья", "Семья и отношения", "🟣", "#ce82ff", 4)
    ]
    
    c.executemany('INSERT OR IGNORE INTO lessons VALUES (?,?,?,?,?,?)', lessons)
    
    # Вопросы для урока 1
    questions_data = [
        (1, "translate", "Hello", '["Привет", "Пока", "Спасибо", "Извините"]', "Привет", 10),
        (1, "translate", "Goodbye", '["Привет", "Пока", "Спасибо", "Извините"]', "Пока", 10),
        (1, "choice", "Выбери правильный перевод: 'Book'", '["Книга", "Ручка", "Стол", "Окно"]', "Книга", 15),
        (1, "fill", "I ___ a student", '["am", "is", "are", "be"]', "am", 20),
        (1, "choice", "Как сказать 'Спасибо'?", '["Thank you", "Hello", "Goodbye", "Please"]', "Thank you", 15),
        
        (2, "translate", "Thank you", '["Спасибо", "Пожалуйста", "Извините", "Привет"]', "Спасибо", 10),
        (2, "choice", "Как сказать 'Как дела?'", '["How are you?", "What is this?", "Where are you?", "Who are you?"]', "How are you?", 15),
        (2, "fill", "My name ___ John", '["is", "am", "are", "be"]', "is", 20),
        (2, "translate", "Please", '["Пожалуйста", "Спасибо", "Извините", "Привет"]', "Пожалуйста", 10),
        
        (3, "translate", "Apple", '["Яблоко", "Банан", "Апельсин", "Виноград"]', "Яблоко", 10),
        (3, "choice", "Выбери напиток", '["Water", "Apple", "Bread", "Cheese"]', "Water", 15),
        (3, "fill", "I want ___ eat", '["to", "for", "at", "in"]', "to", 20),
        
        (4, "translate", "Mother", '["Мама", "Папа", "Брат", "Сестра"]', "Мама", 10),
        (4, "choice", "My ___ is a doctor", '["father", "apple", "book", "water"]', "father", 15)
    ]
    
    c.executemany('INSERT OR IGNORE INTO questions VALUES (?,?,?,?,?,?,?)', 
                  [(None, lesson_id, qtype, question, options, answer, xp) 
                   for lesson_id, qtype, question, options, answer, xp in questions_data])
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)', 
                      (username, password, datetime.now().strftime("%Y-%m-%d %H:%M")))
            db.commit()
            
            user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
            session['user_id'] = user['id']
            session['username'] = username
            
            flash('Добро пожаловать! 🎉')
            return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash('Имя пользователя уже занято')
        finally:
            db.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                         (username, password)).fetchone()
        db.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('С возвращением! 🦉')
            return redirect(url_for('home'))
        else:
            flash('Неверные данные')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    lessons = db.execute('SELECT * FROM lessons ORDER BY order_num').fetchall()
    
    progress = {}
    for lesson in lessons:
        user_progress = db.execute('SELECT * FROM user_progress WHERE user_id = ? AND lesson_id = ?', 
                                 (session['user_id'], lesson['id'])).fetchone()
        progress[lesson['id']] = user_progress
    
    db.close()
    
    return render_template('home.html', user=user, lessons=lessons, progress=progress)

@app.route('/lesson/<int:lesson_id>')
def lesson(lesson_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    lesson_data = db.execute('SELECT * FROM lessons WHERE id = ?', (lesson_id,)).fetchone()
    questions = db.execute('SELECT * FROM questions WHERE lesson_id = ?', (lesson_id,)).fetchall()
    db.close()
    
    return render_template('lesson.html', lesson=lesson_data, questions=questions)

@app.route('/check_answer', methods=['POST'])
def check_answer():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    data = request.get_json()
    question_id = data.get('question_id')
    user_answer = data.get('answer')
    
    db = get_db()
    question = db.execute('SELECT * FROM questions WHERE id = ?', (question_id,)).fetchone()
    
    is_correct = (user_answer == question['correct_answer'])
    response = {'success': True, 'correct': is_correct}
    
    if is_correct:
        db.execute('UPDATE users SET xp = xp + ? WHERE id = ?', 
                  (question['xp_reward'], session['user_id']))
        db.commit()
        response['xp'] = question['xp_reward']
    
    db.close()
    return jsonify(response)

@app.route('/complete_lesson', methods=['POST'])
def complete_lesson():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    data = request.get_json()
    lesson_id = data.get('lesson_id')
    score = data.get('score', 0)
    
    db = get_db()
    
    db.execute('''INSERT OR REPLACE INTO user_progress 
                  (user_id, lesson_id, completed, score, completed_at)
                  VALUES (?, ?, TRUE, ?, ?)''', 
               (session['user_id'], lesson_id, score, datetime.now().strftime("%Y-%m-%d %H:%M")))
    
    db.commit()
    db.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
