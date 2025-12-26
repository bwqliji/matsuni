# bot/utils/formatters.py

def format_report(results: dict) -> str:
    """Форматирование отчета"""
    if not results:
        return "Нет данных для отчета"
    
    report = f"📊 *ОТЧЕТ ЗА ПЕРИОД*\n"
    report += f"────────────────────\n"
    report += f"📅 Период: {results.get('period', 'не указан')}\n"
    report += f"👥 Участников: {results.get('total_members', 0)}\n"
    report += f"💰 Всего матсуни: {results.get('total_matsuni', 0)}\n"
    report += f"────────────────────\n"
    report += f"🏆 *ТОП УЧАСТНИКОВ:*\n"
    
    for i, res in enumerate(results.get('results', [])[:10], 1):
        report += f"{i}. @{res['username']} - {res['total_matsuni']} матсуни "
        report += f"({res['days_active']} дней)\n"
    
    return report

def format_member_list(members: list) -> str:
    """Форматирование списка участников"""
    if not members:
        return "📭 Список участников пуст"
    
    report = f"👥 *СПИСОК УЧАСТНИКОВ*\n"
    report += f"────────────────────\n"
    
    for i, member in enumerate(members, 1):
        status = "✅" if member.get('status', '').lower() == 'активен' else "⏸️"
        report += f"{i}. {status} @{member['username']} "
        report += f"(с {member.get('join_date', '?')})\n"
    
    report += f"────────────────────\n"
    report += f"Всего: {len(members)} участников"
    
    return report