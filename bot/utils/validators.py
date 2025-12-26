# bot/utils/validators.py
import re
from datetime import datetime

def validate_date(date_str: str) -> bool:
    """Проверка даты в формате ГГГГ-ММ-ДД"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_username(username: str) -> bool:
    """Проверка формата username"""
    pattern = r'^[a-zA-Z0-9_.]+$'
    return bool(re.match(pattern, username))