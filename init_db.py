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
            target_language VARCHAR(50) DEFAULT 'Английский',
            native_language VARCHAR(50) DEFAULT 'Русский'
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
        ('Английский', 'en', '🇺🇸'),
        ('Испанский', 'es', '🇪🇸'),
        ('Французский', 'fr', '🇫🇷'),
        ('Немецкий', 'de', '🇩🇪'),
        ('Итальянский', 'it', '🇮🇹'),
        ('Португальский', 'pt', '🇵🇹'),
        ('Русский', 'ru', '🇷🇺')
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO languages (name, code, flag_emoji) VALUES (?, ?, ?)',
        languages
    )
    
    # Добавляем уроки для английского
    english_id = 1
    lessons_data = [
        (english_id, 'Основы 1', 'Выучи основные слова', 1, 1, 10),
        (english_id, 'Основы 2', 'Простые фразы', 1, 2, 10),
        (english_id, 'Приветствия', 'Научись приветствовать людей', 1, 3, 15),
        (english_id, 'Еда', 'Слова о еде', 2, 4, 20),
        (english_id, 'Животные', 'Названия животных', 2, 5, 20),
        (english_id, 'Семья', 'Члены семьи', 2, 6, 20),
    ]
    
    cursor.executemany(
        'INSERT OR IGNORE INTO lessons (language_id, title, description, level, order_index, xp_reward) VALUES (?, ?, ?, ?, ?, ?)',
        lessons_data
    )
    
    # Добавляем упражнения ТОЛЬКО с множественным выбором и сопоставлением
    exercises_data = [
        # Основы 1 - Выбери перевод
        (1, 'multiple_choice', 'Выбери перевод слова "Привет"', 'Hello', '["Hello", "Goodbye", "Thank you", "Please"]', None, 'Hello - приветствие на английском', 1),
        (1, 'multiple_choice', 'Выбери перевод слова "Спасибо"', 'Thank you', '["Thank you", "Please", "Sorry", "Yes"]', None, 'Thank you - выражение благодарности', 2),
        (1, 'multiple_choice', 'Выбери перевод слова "Да"', 'Yes', '["Yes", "No", "Maybe", "OK"]', None, 'Yes - утвердительный ответ', 3),
        (1, 'multiple_choice', 'Выбери перевод слова "Нет"', 'No', '["No", "Yes", "Not", "Never"]', None, 'No - отрицательный ответ', 4),
        (1, 'multiple_choice', 'Выбери перевод слова "Пожалуйста"', 'Please', '["Please", "Thank you", "You are welcome", "Sorry"]', None, 'Please - вежливая просьба', 5),
        
        # Основы 1 - Сопоставь слова
        (1, 'multiple_choice', 'Сопоставь: "Яблоко"', 'Apple', '["Apple", "Orange", "Banana", "Grape"]', None, 'Apple - яблоко', 6),
        (1, 'multiple_choice', 'Сопоставь: "Вода"', 'Water', '["Water", "Coffee", "Tea", "Juice"]', None, 'Water - вода', 7),
        (1, 'multiple_choice', 'Сопоставь: "Дом"', 'House', '["House", "Car", "Tree", "Street"]', None, 'House - дом', 8),
        (1, 'multiple_choice', 'Сопоставь: "Книга"', 'Book', '["Book", "Pen", "Paper", "Notebook"]', None, 'Book - книга', 9),
        
        # Основы 2 - Выбери перевод фраз
        (2, 'multiple_choice', 'Выбери перевод: "Как дела?"', 'How are you?', '["How are you?", "What is your name?", "Where are you from?", "How old are you?"]', None, 'How are you? - вопрос о состоянии', 1),
        (2, 'multiple_choice', 'Выбери перевод: "Меня зовут..."', 'My name is...', '["My name is...", "I am from...", "I live in...", "I am... years old"]', None, 'My name is... - представление', 2),
        (2, 'multiple_choice', 'Выбери перевод: "Я из России"', 'I am from Russia', '["I am from Russia", "I live in Russia", "I like Russia", "I visit Russia"]', None, 'I am from Russia - указание страны происхождения', 3),
        (2, 'multiple_choice', 'Выбери перевод: "Хорошо"', 'Good', '["Good", "Bad", "OK", "Fine"]', None, 'Good - положительная оценка', 4),
        
        # Основы 2 - Сопоставь слова
        (2, 'multiple_choice', 'Сопоставь: "Машина"', 'Car', '["Car", "Bus", "Train", "Bicycle"]', None, 'Car - автомобиль', 5),
        (2, 'multiple_choice', 'Сопоставь: "Красный"', 'Red', '["Red", "Blue", "Green", "Yellow"]', None, 'Red - красный цвет', 6),
        (2, 'multiple_choice', 'Сопоставь: "Большой"', 'Big', '["Big", "Small", "Medium", "Large"]', None, 'Big - большой размер', 7),
        (2, 'multiple_choice', 'Сопоставь: "Быстрый"', 'Fast', '["Fast", "Slow", "Quick", "Rapid"]', None, 'Fast - высокая скорость', 8),
        
        # Приветствия
        (3, 'multiple_choice', 'Выбери утреннее приветствие', 'Good morning', '["Good morning", "Good afternoon", "Good evening", "Good night"]', None, 'Good morning - доброе утро', 1),
        (3, 'multiple_choice', 'Выбери вечернее приветствие', 'Good evening', '["Good evening", "Good morning", "Good afternoon", "Good night"]', None, 'Good evening - добрый вечер', 2),
        (3, 'multiple_choice', 'Как сказать "Приятно познакомиться"?', 'Nice to meet you', '["Nice to meet you", "Nice to see you", "Good to know you", "Happy to meet you"]', None, 'Nice to meet you - при знакомстве', 3),
        (3, 'multiple_choice', 'Выбери прощание на ночь', 'Good night', '["Good night", "Good evening", "Goodbye", "See you"]', None, 'Good night - спокойной ночи', 4),
        
        # Приветствия - вопросы
        (3, 'multiple_choice', 'Как спросить "Как тебя зовут?"', 'What is your name?', '["What is your name?", "How are you?", "Where are you from?", "How old are you?"]', None, 'What is your name? - вопрос об имени', 5),
        (3, 'multiple_choice', 'Как спросить "Откуда ты?"', 'Where are you from?', '["Where are you from?", "What is your name?", "How are you?", "What time is it?"]', None, 'Where are you from? - вопрос о происхождении', 6),
        
        # Еда
        (4, 'multiple_choice', 'Сопоставь: "Хлеб"', 'Bread', '["Bread", "Butter", "Cheese", "Milk"]', None, 'Bread - хлеб', 1),
        (4, 'multiple_choice', 'Сопоставь: "Молоко"', 'Milk', '["Milk", "Water", "Juice", "Coffee"]', None, 'Milk - молоко', 2),
        (4, 'multiple_choice', 'Сопоставь: "Яйцо"', 'Egg', '["Egg", "Apple", "Banana", "Orange"]', None, 'Egg - яйцо', 3),
        (4, 'multiple_choice', 'Сопоставь: "Мясо"', 'Meat', '["Meat", "Fish", "Chicken", "Beef"]', None, 'Meat - мясо', 4),
        
        # Еда - фразы
        (4, 'multiple_choice', 'Как сказать "Я голоден"?', 'I am hungry', '["I am hungry", "I am thirsty", "I am tired", "I am happy"]', None, 'I am hungry - выражение голода', 5),
        (4, 'multiple_choice', 'Как сказать "Это вкусно"?', 'It is delicious', '["It is delicious", "It is bad", "It is OK", "It is terrible"]', None, 'It is delicious - комплимент еде', 6),
        
        # Животные
        (5, 'multiple_choice', 'Сопоставь: "Собака"', 'Dog', '["Dog", "Cat", "Bird", "Fish"]', None, 'Dog - собака', 1),
        (5, 'multiple_choice', 'Сопоставь: "Кошка"', 'Cat', '["Cat", "Dog", "Mouse", "Rabbit"]', None, 'Cat - кошка', 2),
        (5, 'multiple_choice', 'Сопоставь: "Птица"', 'Bird', '["Bird", "Fish", "Butterfly", "Bee"]', None, 'Bird - птица', 3),
        (5, 'multiple_choice', 'Сопоставь: "Рыба"', 'Fish', '["Fish", "Shark", "Dolphin", "Whale"]', None, 'Fish - рыба', 4),
        
        # Животные - дикие
        (5, 'multiple_choice', 'Сопоставь: "Лев"', 'Lion', '["Lion", "Tiger", "Bear", "Wolf"]', None, 'Lion - лев', 5),
        (5, 'multiple_choice', 'Сопоставь: "Слон"', 'Elephant', '["Elephant", "Giraffe", "Zebra", "Hippo"]', None, 'Elephant - слон', 6),
        
        # Семья
        (6, 'multiple_choice', 'Сопоставь: "Мама"', 'Mother', '["Mother", "Father", "Sister", "Brother"]', None, 'Mother - мать', 1),
        (6, 'multiple_choice', 'Сопоставь: "Папа"', 'Father', '["Father", "Mother", "Grandfather", "Uncle"]', None, 'Father - отец', 2),
        (6, 'multiple_choice', 'Сопоставь: "Брат"', 'Brother', '["Brother", "Sister", "Cousin", "Friend"]', None, 'Brother - брат', 3),
        (6, 'multiple_choice', 'Сопоставь: "Сестра"', 'Sister', '["Sister", "Brother", "Aunt", "Niece"]', None, 'Sister - сестра', 4),
        
        # Семья - расширенная
        (6, 'multiple_choice', 'Сопоставь: "Бабушка"', 'Grandmother', '["Grandmother", "Grandfather", "Mother", "Aunt"]', None, 'Grandmother - бабушка', 5),
        (6, 'multiple_choice', 'Сопоставь: "Дедушка"', 'Grandfather', '["Grandfather", "Grandmother", "Father", "Uncle"]', None, 'Grandfather - дедушка', 6),
    ]
    
    for exercise in exercises_data:
        cursor.execute('''
            INSERT OR IGNORE INTO exercises 
            (lesson_id, type, question, correct_answer, options, audio_file, explanation, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', exercise)
    
    # Добавляем тестовых пользователей
    test_users = [
        ('тестовый', 'test@example.com', 'password123', 150, 7),
        ('мария', 'maria@example.com', 'password123', 450, 12),
        ('иван', 'ivan@example.com', 'password123', 890, 25),
        ('анна', 'anna@example.com', 'password123', 120, 3),
        ('сергей', 'sergey@example.com', 'password123', 1200, 45),
    ]
    
    for username, email, password, xp, streak in test_users:
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password_hash, xp, streak)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, email, password_hash, xp, streak))
    
    conn.commit()
    conn.close()
    print("База данных успешно инициализирована!")

if __name__ == '__main__':
    init_database()
