import sqlite3
import bcrypt
from datetime import datetime, timedelta
import json

def init_database():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(80) UNIQUE NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            xp INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_login DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            target_language VARCHAR(50) DEFAULT 'English',
            native_language VARCHAR(50) DEFAULT 'Russian'
        )
    ''')
    
    # Таблица языков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS languages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(50) NOT NULL,
            code VARCHAR(5) NOT NULL,
            flag_emoji VARCHAR(10)
        )
    ''')
    
    # Таблица уроков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_id INTEGER,
            title VARCHAR(100) NOT NULL,
            description TEXT,
            level INTEGER DEFAULT 1,
            order_index INTEGER,
            xp_reward INTEGER DEFAULT 10,
            FOREIGN KEY (language_id) REFERENCES languages (id)
        )
    ''')
    
    # Таблица упражнений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER,
            type VARCHAR(20) NOT NULL,
            question TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            options TEXT,
            audio_file VARCHAR(100),
            explanation TEXT,
            order_index INTEGER,
            FOREIGN KEY (lesson_id) REFERENCES lessons (id)
        )
    ''')
    
    # Таблица прогресса пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            lesson_id INTEGER,
            completed BOOLEAN DEFAULT FALSE,
            score INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            attempts INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (lesson_id) REFERENCES lessons (id)
        )
    ''')
    
    # Таблица ответов пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            exercise_id INTEGER,
            user_answer TEXT,
            is_correct BOOLEAN,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (exercise_id) REFERENCES exercises (id)
        )
    ''')
    
    # Добавляем языки
    languages = [
        ('English', 'en', '🇺🇸'),
        ('Spanish', 'es', '🇪🇸'),
        ('French', 'fr', '🇫🇷'),
        ('German', 'de', '🇩🇪'),
        ('Italian', 'it', '🇮🇹'),
        ('Portuguese', 'pt', '🇵🇹'),
        ('Russian', 'ru', '🇷🇺')
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO languages (name, code, flag_emoji) VALUES (?, ?, ?)',
        languages
    )
    
    # Добавляем уроки для английского
    english_id = 1
    lessons_data = [
        (english_id, 'Basics 1', 'Learn basic words and phrases', 1, 1, 10),
        (english_id, 'Basics 2', 'More basic vocabulary', 1, 2, 10),
        (english_id, 'Greetings', 'Learn how to greet people', 1, 3, 15),
        (english_id, 'Food', 'Food and restaurant vocabulary', 2, 4, 20),
        (english_id, 'Animals', 'Animal names and descriptions', 2, 5, 20),
        (english_id, 'Travel', 'Travel and transportation', 3, 6, 25),
        (english_id, 'Business', 'Business and work vocabulary', 3, 7, 25),
        (english_id, 'Medical', 'Medical terms and phrases', 4, 8, 30),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO lessons (language_id, title, description, level, order_index, xp_reward) VALUES (?, ?, ?, ?, ?, ?)',
        lessons_data
    )
    
    # Добавляем упражнения
    exercises_data = [
        # Basics 1
        (1, 'translation', 'Hello', 'Привет', None, None, 'Basic greeting', 1),
        (1, 'translation', 'Goodbye', 'До свидания', None, None, 'Farewell expression', 2),
        (1, 'translation', 'Thank you', 'Спасибо', None, None, 'Expression of gratitude', 3),
        (1, 'translation', 'Please', 'Пожалуйста', None, None, 'Polite request', 4),
        (1, 'multiple_choice', 'Apple', 'Яблоко', '["Яблоко", "Апельсин", "Банан", "Груша"]', None, 'Common fruit', 5),
        (1, 'multiple_choice', 'Book', 'Книга', '["Книга", "Ручка", "Стол", "Стул"]', None, 'Reading material', 6),
        
        # Basics 2
        (2, 'translation', 'Water', 'Вода', None, None, 'Essential liquid', 1),
        (2, 'translation', 'House', 'Дом', None, None, 'Living place', 2),
        (2, 'multiple_choice', 'Car', 'Машина', '["Машина", "Велосипед", "Самолет", "Поезд"]', None, 'Vehicle', 3),
        (2, 'translation', 'My name is...', 'Меня зовут...', None, None, 'Self-introduction', 4),
        
        # Greetings
        (3, 'translation', 'How are you?', 'Как дела?', None, None, 'Common greeting question', 1),
        (3, 'translation', 'Good morning', 'Доброе утро', None, None, 'Morning greeting', 2),
        (3, 'multiple_choice', 'Good night', 'Спокойной ночи', '["Спокойной ночи", "Добрый день", "Добрый вечер", "Привет"]', None, 'Evening farewell', 3),
    ]
    
    for exercise in exercises_data:
        cursor.execute('''
            INSERT OR IGNORE INTO exercises 
            (lesson_id, type, question, correct_answer, options, audio_file, explanation, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', exercise)
    
    # Добавляем тестового пользователя
    password_hash = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt())
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, email, password_hash, xp, streak)
        VALUES (?, ?, ?, ?, ?)
    ''', ('testuser', 'test@example.com', password_hash, 150, 7))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()