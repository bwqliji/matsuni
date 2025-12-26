from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from ..database.gsheets import get_db

logger = logging.getLogger(__name__)

class MatsuniCalculator:
    """Калькулятор матсуни с поддержкой исключений"""
    
    def __init__(self, rules: Dict = None):
        self.db = get_db()
        self.rules = rules or {
            'max_per_day': 2,
            'like_only': 1,
            'comment_only': 2,
            'like_comment': 2,
        }
    
    def calculate_for_post(self, post_data: Dict, activities: List[Dict]) -> List[Dict]:
        """Рассчитать матсуни для поста"""
        post_name = post_data.get('name', '')
        post_date = post_data.get('date', '')
        
        # Получаем исключения для этого поста
        exclusions = self.db.get_exclusions(post_name)
        excluded_users = {ex['username'] for ex in exclusions}
        
        results = []
        for activity in activities:
            username = activity.get('username', '')
            
            # Проверяем исключения
            if username in excluded_users:
                logger.info(f"User {username} excluded from post {post_name}")
                continue
            
            has_like = activity.get('has_like', False)
            has_comment = activity.get('has_comment', False)
            
            # Применяем правила
            if has_comment:
                # Если есть комментарий - всегда 2 матсуни
                matsuni = self.rules['like_comment']
            elif has_like:
                matsuni = self.rules['like_only']
            else:
                matsuni = 0
            
            # Проверяем дневной лимит
            daily_limit = self._check_daily_limit(username, post_date, matsuni)
            if daily_limit < matsuni:
                logger.info(f"Daily limit for {username} on {post_date}: {daily_limit}")
                matsuni = daily_limit
            
            results.append({
                'username': username,
                'has_like': has_like,
                'has_comment': has_comment,
                'matsuni': matsuni,
                'post_name': post_name,
                'post_date': post_date
            })
        
        return results
    
    def _check_daily_limit(self, username: str, date: str, new_matsuni: int) -> int:
        """Проверить дневной лимит"""
        # Получаем все активности пользователя за эту дату
        ws = self.db.get_worksheet('Активность')
        data = ws.get_all_records()
        
        daily_total = 0
        for row in data:
            if row['Username'] == username:
                activity_date = row['Время проверки'].split()[0]
                if activity_date == date:
                    daily_total += int(row.get('Матсуни', 0))
        
        remaining = self.rules['max_per_day'] - daily_total
        return min(new_matsuni, max(0, remaining))
    
    def calculate_period_totals(self, start_date: str, end_date: str) -> Dict:
        """Рассчитать итоги за период"""
        result = self.db.calculate_totals(start_date, end_date)
        
        # Добавляем дополнительные метрики
        for res in result['results']:
            # Рассчитываем эффективность
            total_days = result['total_days']
            active_days = res['days_active']
            
            res['efficiency'] = round((active_days / total_days) * 100, 1) if total_days > 0 else 0
            
            # Оцениваем активность
            if res['avg_matsuni'] >= 1.5:
                res['activity_level'] = 'высокая'
            elif res['avg_matsuni'] >= 0.5:
                res['activity_level'] = 'средняя'
            else:
                res['activity_level'] = 'низкая'
        
        return result
    
    def generate_rankings(self, period_data: Dict) -> List[Dict]:
        """Сгенерировать рейтинги"""
        results = period_data['results']
        
        # Топ по общему количеству матсуни
        top_total = sorted(results, key=lambda x: x['total_matsuni'], reverse=True)[:10]
        
        # Топ по средней активности
        top_avg = sorted(results, key=lambda x: x['avg_matsuni'], reverse=True)[:10]
        
        # Топ по дням активности
        top_days = sorted(results, key=lambda x: x['days_active'], reverse=True)[:10]
        
        # Самые стабильные (минимальное отклонение)
        if len(results) >= 3:
            stable = sorted(results, key=lambda x: abs(x['avg_matsuni'] - 1))[:5]
        else:
            stable = []
        
        return {
            'top_total': top_total,
            'top_avg': top_avg,
            'top_days': top_days,
            'most_stable': stable,
            'period': period_data['period']
        }
    
    def predict_next_period(self, user_data: Dict) -> Dict:
        """Предсказать результаты на следующий период"""
        # Простая линейная регрессия
        avg_matsuni = user_data.get('avg_matsuni', 0)
        days_active = user_data.get('days_active', 0)
        total_days = user_data.get('total_days_observed', 30)
        
        if total_days == 0:
            return {'predicted_matsuni': 0, 'confidence': 0}
        
        activity_rate = days_active / total_days
        predicted_days = activity_rate * 30  # На 30 дней вперед
        predicted_matsuni = avg_matsuni * predicted_days
        
        # Уверенность предсказания (основана на количестве данных)
        confidence = min(days_active / 10, 1.0)  # Максимум после 10 дней наблюдений
        
        return {
            'predicted_matsuni': round(predicted_matsuni, 1),
            'predicted_days': round(predicted_days, 1),
            'confidence': round(confidence, 2)
        }

# Глобальный экземпляр калькулятора
calculator = MatsuniCalculator()