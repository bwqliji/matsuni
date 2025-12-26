import os
from datetime import timedelta
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / 'logs'
DATA_DIR = BASE_DIR / 'data'

# Создаем директории
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администраторов
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Google Sheets
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_CREDENTIALS = BASE_DIR / 'credentials.json'

# Правила матсуни
MATSUNI_RULES = {
    'max_per_day': 2,
    'like_only': 1,
    'like_comment': 2,
    'comment_only': 2,  # Комментарий без лайка = 2 матсуни
}

# Исключения (по умолчанию)
DEFAULT_EXCLUSIONS = {
    'vibro': [],  # Участники, которые никогда не проходят в vibro
    'test': [],   # Тестовые исключения
}

# OCR настройки
OCR_CONFIG = {
    'lang': 'eng+rus',
    'config': '--oem 3 --psm 6',
    'whitelist': 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._-',
}

# Настройки кэша
CACHE_CONFIG = {
    'ttl': 300,  # 5 минут
    'max_size': 1000,
}

# Логирование
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'bot.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'bot': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}