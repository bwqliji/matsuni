# bot/keyboards/main_menu.py
from telegram import ReplyKeyboardMarkup

def get_main_keyboard():
    """Основная клавиатура"""
    keyboard = [
        ['➕ Добавить участника', '📋 Список участников'],
        ['📝 Новый пост', '🧮 Подсчитать итог'],
        ['⚠️ Добавить исключение', '📤 Экспорт в Excel'],
        ['❓ Помощь']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_post_keyboard():
    """Клавиатура для постов"""
    keyboard = [
        ['✅ Завершить этап', '❌ Отмена']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_yes_no_keyboard():
    """Да/Нет клавиатура"""
    keyboard = [
        ['✅ Да', '❌ Нет']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_edit_keyboard():
    """Клавиатура редактирования"""
    keyboard = [
        ['✏️ Исправить', '➕ Добавить'],
        ['🗑️ Удалить', '🔙 Назад']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_calculate_keyboard():
    """Клавиатура для подсчета"""
    keyboard = [
        ['📊 Подробный отчет', '📤 Экспорт в Excel'],
        ['🔙 Назад']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)