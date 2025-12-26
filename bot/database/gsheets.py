import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import pandas as pd
import cachetools
from ..utils.validators import validate_date, validate_username
from ..database.cache import cache_manager
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsDB:
    """Улучшенная работа с Google Sheets"""
    
    def __init__(self, sheet_id: str, credentials_file: str):
        self.sheet_id = sheet_id
        self.credentials_file = credentials_file
        self._client = None
        self._sheet = None
        self._worksheets = {}
        
    @property
    def client(self):
        """Ленивая инициализация клиента"""
        if self._client is None:
            try:
                scope = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                creds = Credentials.from_service_account_file(
                    self.credentials_file, 
                    scopes=scope
                )
                self._client = gspread.authorize(creds)
                self._sheet = self._client.open_by_key(self.sheet_id)
                self._load_worksheets()
                logger.info("Google Sheets client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Google Sheets: {e}")
                raise
        return self._client
    
    def _load_worksheets(self):
        """Загрузка всех листов"""
        worksheets = self._sheet.worksheets()
        for ws in worksheets:
            self._worksheets[ws.title] = ws
    
    def get_worksheet(self, name: str, create_if_missing: bool = True):
        """Получить лист по имени"""
        if name not in self._worksheets and create_if_missing:
            try:
                ws = self._sheet.add_worksheet(title=name, rows=1000, cols=20)
                self._worksheets[name] = ws
                self._init_worksheet_structure(ws, name)
                logger.info(f"Created new worksheet: {name}")
            except Exception as e:
                logger.error(f"Failed to create worksheet {name}: {e}")
                raise
        return self._worksheets.get(name)
    
    def _init_worksheet_structure(self, worksheet, name: str):
        """Инициализация структуры листа"""
        headers = {
            'Участники': ['Username', 'Дата добавления', 'Статус', 'Телеграм ID'],
            'Посты': ['Номер', 'Название', 'Дата', 'Тип', 'Статус', 'Комментарий'],
            'Активность': ['ID поста', 'Username', 'Лайк', 'Комментарий', 'Матсуни', 'Время проверки'],
            'Исключения': ['Username', 'Название поста', 'Причина', 'Дата', 'Активно'],
            'Итоги': ['Период', 'Username', 'Дней активности', 'Всего матсуни', 'Среднее', 'Рейтинг'],
            'Настройки': ['Ключ', 'Значение', 'Описание'],
        }
        
        if name in headers:
            worksheet.clear()
            worksheet.append_row(headers[name])
            # Форматирование заголовков
            worksheet.format('A1:Z1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
            })
    
    @cachetools.cached(cache=cache_manager.get_cache('members'))
    def get_members(self, active_only: bool = True) -> List[Dict]:
        """Получить всех участников"""
        ws = self.get_worksheet('Участники')
        data = ws.get_all_records()
        
        members = []
        for row in data:
            if active_only and row.get('Статус', 'активен').lower() != 'активен':
                continue
            members.append({
                'username': row['Username'],
                'join_date': row['Дата добавления'],
                'status': row.get('Статус', 'активен'),
                'telegram_id': row.get('Телеграм ID')
            })
        
        return members
    
    def add_member(self, username: str, join_date: str = None, telegram_id: str = None) -> bool:
        """Добавить участника"""
        validate_username(username)
        
        if not join_date:
            join_date = datetime.now().strftime('%Y-%m-%d')
        else:
            validate_date(join_date)
        
        ws = self.get_worksheet('Участники')
        ws.append_row([username, join_date, 'активен', telegram_id or ''])
        
        # Сброс кэша
        cache_manager.clear_cache('members')
        logger.info(f"Member added: {username}")
        return True
    
    def update_member_status(self, username: str, status: str) -> bool:
        """Обновить статус участника"""
        ws = self.get_worksheet('Участники')
        data = ws.get_all_values()
        
        for i, row in enumerate(data[1:], start=2):  # Пропускаем заголовок
            if row[0] == username:
                ws.update_cell(i, 3, status)  # Колонка статуса
                cache_manager.clear_cache('members')
                logger.info(f"Member {username} status updated to {status}")
                return True
        
        return False
    
    @cachetools.cached(cache=cache_manager.get_cache('exclusions'))
    def get_exclusions(self, post_name: str = None) -> List[Dict]:
        """Получить исключения"""
        ws = self.get_worksheet('Исключения')
        data = ws.get_all_records()
        
        exclusions = []
        for row in data:
            if row['Активно'].lower() != 'да':
                continue
            if post_name and row['Название поста'] != post_name:
                continue
            
            exclusions.append({
                'username': row['Username'],
                'post_name': row['Название поста'],
                'reason': row['Причина'],
                'date': row['Дата']
            })
        
        return exclusions
    
    def add_exclusion(self, username: str, post_name: str, reason: str = '') -> bool:
        """Добавить исключение"""
        ws = self.get_worksheet('Исключения')
        ws.append_row([
            username,
            post_name,
            reason,
            datetime.now().strftime('%Y-%m-%d'),
            'да'
        ])
        
        cache_manager.clear_cache('exclusions')
        logger.info(f"Exclusion added: {username} for {post_name}")
        return True
    
    def save_activity(self, post_data: Dict, activities: List[Dict]) -> bool:
        """Сохранить активность по посту"""
        ws = self.get_worksheet('Активность')
        
        rows = []
        for activity in activities:
            rows.append([
                post_data['id'],
                activity['username'],
                'да' if activity.get('has_like') else 'нет',
                'да' if activity.get('has_comment') else 'нет',
                activity.get('matsuni', 0),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        if rows:
            ws.append_rows(rows)
        
        # Обновляем статус поста
        post_ws = self.get_worksheet('Посты')
        post_ws.append_row([
            post_data['id'],
            post_data['name'],
            post_data['date'],
            post_data.get('type', 'обычный'),
            'обработан',
            post_data.get('comment', '')
        ])
        
        logger.info(f"Activity saved for post {post_data['id']}: {len(activities)} records")
        return True
    
    def calculate_totals(self, start_date: str, end_date: str) -> Dict:
        """Подсчитать итоги за период"""
        validate_date(start_date)
        validate_date(end_date)
        
        # Получаем все активности за период
        ws = self.get_worksheet('Активность')
        data = ws.get_all_records()
        
        activities = []
        for row in data:
            activity_date = row['Время проверки'].split()[0]
            if start_date <= activity_date <= end_date:
                activities.append(row)
        
        # Группируем по участникам
        members_ws = self.get_worksheet('Участники')
        members = {row['Username']: row for row in members_ws.get_all_records()}
        
        results = {}
        for activity in activities:
            username = activity['Username']
            if username not in members:
                continue
            
            if username not in results:
                results[username] = {
                    'username': username,
                    'days_active': set(),
                    'total_matsuni': 0,
                    'activities': []
                }
            
            activity_date = activity['Время проверки'].split()[0]
            results[username]['days_active'].add(activity_date)
            results[username]['total_matsuni'] += int(activity['Матсуни'])
            results[username]['activities'].append(activity)
        
        # Преобразуем в список и сортируем
        final_results = []
        for username, data in results.items():
            days_active = len(data['days_active'])
            avg_matsuni = data['total_matsuni'] / days_active if days_active > 0 else 0
            
            final_results.append({
                'username': username,
                'days_active': days_active,
                'total_matsuni': data['total_matsuni'],
                'avg_matsuni': round(avg_matsuni, 2),
                'join_date': members[username].get('Дата добавления', ''),
                'status': members[username].get('Статус', 'активен')
            })
        
        # Сортировка по total_matsuni (по убыванию)
        final_results.sort(key=lambda x: x['total_matsuni'], reverse=True)
        
        # Добавляем рейтинг
        for i, result in enumerate(final_results, 1):
            result['rank'] = i
        
        # Сохраняем в лист Итоги
        totals_ws = self.get_worksheet('Итоги')
        period_id = f"{start_date}_{end_date}"
        
        # Очищаем старые записи для этого периода
        existing_data = totals_ws.get_all_values()
        rows_to_keep = [existing_data[0]]  # Заголовок
        
        for row in existing_data[1:]:
            if len(row) > 0 and row[0] != period_id:
                rows_to_keep.append(row)
        
        # Добавляем новые результаты
        new_rows = []
        for result in final_results:
            new_rows.append([
                period_id,
                result['username'],
                result['days_active'],
                result['total_matsuni'],
                result['avg_matsuni'],
                result['rank']
            ])
        
        # Обновляем весь лист
        totals_ws.clear()
        totals_ws.update(rows_to_keep + new_rows, value_input_option='RAW')
        
        return {
            'period': f"{start_date} - {end_date}",
            'total_days': (datetime.strptime(end_date, '%Y-%m-%d') - 
                          datetime.strptime(start_date, '%Y-%m-%d')).days + 1,
            'total_members': len(final_results),
            'total_matsuni': sum(r['total_matsuni'] for r in final_results),
            'results': final_results
        }
    
    def export_to_excel(self, period: str = None) -> bytes:
        """Экспорт данных в Excel"""
        import io
        
        # Создаем Excel writer
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Экспортируем все листы
            for sheet_name in ['Участники', 'Посты', 'Активность', 'Итоги', 'Исключения']:
                ws = self.get_worksheet(sheet_name)
                data = ws.get_all_values()
                
                if data:
                    df = pd.DataFrame(data[1:], columns=data[0])
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Добавляем сводный отчет
            if period:
                totals = self.calculate_totals(*period.split('_'))
                df_totals = pd.DataFrame(totals['results'])
                df_totals.to_excel(writer, sheet_name='Сводный_отчет', index=False)
        
        output.seek(0)
        return output.read()

# Глобальный экземпляр базы данных
db_instance = None

def get_db():
    """Получить экземпляр базы данных"""
    global db_instance
    if db_instance is None:
        from config.settings import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS
        db_instance = GoogleSheetsDB(GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS)
    return db_instance