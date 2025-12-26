import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from config.settings import BOT_TOKEN, ADMIN_IDS, LOGGING_CONFIG
from bot.database.gsheets import get_db
from bot.services.image_ocr import image_processor
from bot.services.matsuni_calc import calculator
from bot.services.report_gen import ReportGenerator
from bot.keyboards.main_menu import (
    get_main_keyboard, get_post_keyboard, get_yes_no_keyboard,
    get_edit_keyboard, get_calculate_keyboard
)
from bot.utils.validators import validate_date, validate_username
from bot.utils.formatters import format_report, format_member_list
import io

# Настройка логирования
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

# Состояния диалога
class States:
    ADD_MEMBER = 1
    ADD_MEMBER_DATE = 2
    POST_NAME = 3
    POST_DATE = 4
    POST_TYPE = 5
    POST_LIKES = 6
    POST_COMMENTS = 7
    POST_CONFIRM = 8
    CALCULATE_START = 9
    CALCULATE_END = 10
    EDIT_CHOICE = 11
    EDIT_USERNAME = 12
    EDIT_POST = 13
    EDIT_ACTION = 14
    EXCLUSION_ADD = 15
    EXCLUSION_POST = 16
    EXCLUSION_REASON = 17

class MatsuniBot:
    """Главный класс бота"""
    
    def __init__(self):
        self.db = get_db()
        self.report_gen = ReportGenerator()
        self.user_sessions: Dict[int, Dict] = {}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        await update.message.reply_text(
            "👋 *Добро пожаловать в бот для подсчета матсуни!*\n\n"
            "*Основные функции:*\n"
            "• 📝 Добавление/управление участниками\n"
            "• 📊 Обработка постов со скриншотами\n"
            "• 🧮 Автоматический подсчет матсуни\n"
            "• ⚠️ Исключения для конкретных постов\n"
            "• 📈 Детальные отчеты и аналитика\n\n"
            "Выберите действие в меню ниже:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )
    
    async def add_member_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать добавление участника"""
        await update.message.reply_text(
            "👤 *Добавление участника*\n\n"
            "Введите username (без @):\n"
            "Пример: `username123`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None
        )
        return States.ADD_MEMBER
    
    async def add_member_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка username участника"""
        username = update.message.text.strip()
        
        if not validate_username(username):
            await update.message.reply_text(
                "❌ *Некорректный username!*\n"
                "Используйте только буквы, цифры, точки и подчеркивания.\n"
                "Попробуйте еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return States.ADD_MEMBER
        
        # Сохраняем во временные данные
        context.user_data['new_member'] = {'username': username}
        
        await update.message.reply_text(
            f"✅ Username `{username}` принят.\n\n"
            "Введите дату добавления участника (ГГГГ-ММ-ДД):\n"
            f"*Текущая дата:* `{datetime.now().strftime('%Y-%m-%d')}`\n"
            "Или нажмите /skip для использования текущей даты",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.ADD_MEMBER_DATE
    
    async def add_member_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка даты добавления"""
        if update.message.text == '/skip':
            join_date = datetime.now().strftime('%Y-%m-%d')
        else:
            join_date = update.message.text.strip()
            
            if not validate_date(join_date):
                await update.message.reply_text(
                    "❌ *Некорректная дата!*\n"
                    "Используйте формат ГГГГ-ММ-ДД\n"
                    "Попробуйте еще раз:",
                    parse_mode=ParseMode.MARKDOWN
                )
                return States.ADD_MEMBER_DATE
        
        member_data = context.user_data['new_member']
        username = member_data['username']
        
        try:
            # Добавляем в базу
            self.db.add_member(username, join_date)
            
            await update.message.reply_text(
                f"✅ *Участник добавлен!*\n\n"
                f"• 👤 Username: `{username}`\n"
                f"• 📅 Дата добавления: `{join_date}`\n"
                f"• 🆔 ID в базе: `{hash(username) % 10000:04d}`\n\n"
                "Участник теперь будет учитываться в подсчетах.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard()
            )
            
            # Очищаем временные данные
            del context.user_data['new_member']
            
        except Exception as e:
            logger.error(f"Error adding member: {e}")
            await update.message.reply_text(
                "❌ *Ошибка при добавлении!*\n"
                "Попробуйте позже или проверьте логи.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard()
            )
        
        return ConversationHandler.END
    
    async def list_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список всех участников"""
        try:
            members = self.db.get_members()
            
            if not members:
                await update.message.reply_text("📭 Список участников пуст.")
                return
            
            # Форматируем список
            message = format_member_list(members)
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error listing members: {e}")
            await update.message.reply_text(
                "❌ Ошибка при получении списка участников."
            )
    
    async def new_post_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать обработку нового поста"""
        # Сбрасываем сессию
        context.user_data['post_session'] = {
            'images_likes': [],
            'images_comments': [],
            'found_likes': set(),
            'found_comments': set()
        }
        
        await update.message.reply_text(
            "📝 *Обработка нового поста*\n\n"
            "Введите название поста:\n"
            "Пример: `vibro`, `art_day`, `фото_конкурс`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None
        )
        return States.POST_NAME
    
    async def process_post_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия поста"""
        post_name = update.message.text.strip()
        context.user_data['post_session']['name'] = post_name
        
        # Проверяем исключения для этого поста
        exclusions = self.db.get_exclusions(post_name)
        if exclusions:
            excluded_users = ', '.join([f"@{ex['username']}" for ex in exclusions])
            await update.message.reply_text(
                f"⚠️ *Внимание!* Для поста `{post_name}` есть исключения:\n"
                f"{excluded_users}\n\n"
                "Эти участники не будут учитываться при проверке.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        await update.message.reply_text(
            f"✅ Название поста: `{post_name}`\n\n"
            "Введите дату поста (ГГГГ-ММ-ДД):\n"
            f"*Текущая дата:* `{datetime.now().strftime('%Y-%m-%d')}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.POST_DATE
    
    async def process_post_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка даты поста"""
        date_str = update.message.text.strip()
        
        if not validate_date(date_str):
            await update.message.reply_text(
                "❌ *Некорректная дата!*\n"
                "Используйте формат ГГГГ-ММ-ДД\n"
                "Попробуйте еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return States.POST_DATE
        
        context.user_data['post_session']['date'] = date_str
        
        # Получаем участников, добавленных до этой даты
        members = [m['username'] for m in self.db.get_members()]
        members_before = self.db.get_members_before_date(date_str)
        
        if not members_before:
            await update.message.reply_text(
                "❌ *Нет участников для проверки!*\n"
                "Все участники добавлены после этой даты.",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END
        
        context.user_data['post_session']['members_to_check'] = members_before
        
        await update.message.reply_text(
            f"✅ *Параметры поста:*\n\n"
            f"• 📝 Название: `{context.user_data['post_session']['name']}`\n"
            f"• 📅 Дата: `{date_str}`\n"
            f"• 👥 Участников для проверки: `{len(members_before)}`\n\n"
            "Теперь отправьте *скриншоты с лайками*.\n"
            "Можно отправить несколько фото за раз.\n"
            "Когда закончите, нажмите *Завершить этап*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_post_keyboard()
        )
        return States.POST_LIKES
    
    async def process_likes_images(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка скриншотов с лайками"""
        if update.message.text == '✅ Завершить этап':
            await update.message.reply_text(
                "✅ *Этап с лайками завершен!*\n\n"
                "Теперь отправьте *скриншоты с комментариями*.\n"
                "Если комментариев нет, нажмите *Завершить этап*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_post_keyboard()
            )
            return States.POST_COMMENTS
        
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            image_bytes = await file.download_as_bytearray()
            
            # Сохраняем изображение
            context.user_data['post_session']['images_likes'].append(bytes(image_bytes))
            
            # Обрабатываем в фоне
            members = context.user_data['post_session']['members_to_check']
            result = image_processor._process_single_image(bytes(image_bytes), members)
            
            # Добавляем найденных
            context.user_data['post_session']['found_likes'].update(result['likes'])
            
            await update.message.reply_text(
                f"✅ Скриншот обработан.\n"
                f"Найдено лайков: *{len(context.user_data['post_session']['found_likes'])}*",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return States.POST_LIKES
    
    async def process_comments_images(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка скриншотов с комментариями"""
        if update.message.text == '✅ Завершить этап':
            # Переходим к подтверждению
            return await self.confirm_post(update, context)
        
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            image_bytes = await file.download_as_bytearray()
            
            # Сохраняем изображение
            context.user_data['post_session']['images_comments'].append(bytes(image_bytes))
            
            # Обрабатываем в фоне
            members = context.user_data['post_session']['members_to_check']
            result = image_processor._process_single_image(bytes(image_bytes), members)
            
            # Добавляем найденных
            context.user_data['post_session']['found_comments'].update(result['comments'])
            
            await update.message.reply_text(
                f"✅ Скриншот обработан.\n"
                f"Найдено комментариев: *{len(context.user_data['post_session']['found_comments'])}*",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return States.POST_COMMENTS
    
    async def confirm_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и сохранение поста"""
        session = context.user_data['post_session']
        
        # Создаем ID поста
        post_id = f"{session['name']}_{session['date']}_{datetime.now().strftime('%H%M%S')}"
        
        # Рассчитываем активность для каждого участника
        activities = []
        for member in session['members_to_check']:
            has_like = member in session['found_likes']
            has_comment = member in session['found_comments']
            
            activities.append({
                'username': member,
                'has_like': has_like,
                'has_comment': has_comment
            })
        
        # Рассчитываем матсуни
        post_data = {
            'id': post_id,
            'name': session['name'],
            'date': session['date']
        }
        
        results = calculator.calculate_for_post(post_data, activities)
        
        # Формируем отчет для подтверждения
        total_matsuni = sum(r['matsuni'] for r in results)
        active_members = [r for r in results if r['matsuni'] > 0]
        
        report = (
            f"📊 *ПОДТВЕРЖДЕНИЕ ПОСТА*\n\n"
            f"*Название:* {session['name']}\n"
            f"*Дата:* {session['date']}\n"
            f"*Участников проверено:* {len(activities)}\n"
            f"*Активных:* {len(active_members)}\n"
            f"*Лайков найдено:* {len(session['found_likes'])}\n"
            f"*Комментариев найдено:* {len(session['found_comments'])}\n"
            f"*Всего матсуни:* {total_matsuni}\n\n"
            f"*Топ активных:*\n"
        )
        
        for i, member in enumerate(active_members[:5], 1):
            report += f"{i}. @{member['username']} - {member['matsuni']} матсуни\n"
        
        if len(active_members) > 5:
            report += f"... и еще {len(active_members) - 5} участников\n"
        
        keyboard = [
            [InlineKeyboardButton("✅ Сохранить", callback_data=f"save_post_{post_id}")],
            [InlineKeyboardButton("✏️ Редактировать", callback_data="edit_post")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_post")]
        ]
        
        await update.message.reply_text(
            report,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Сохраняем результаты для сохранения
        context.user_data['post_results'] = {
            'post_data': post_data,
            'results': results
        }
        
        return States.POST_CONFIRM
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка inline кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith('save_post_'):
            # Сохраняем пост
            post_results = context.user_data.get('post_results')
            if post_results:
                try:
                    self.db.save_activity(
                        post_results['post_data'],
                        post_results['results']
                    )
                    
                    await query.edit_message_text(
                        "✅ *Пост успешно сохранен!*\n"
                        "Данные добавлены в таблицу.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Очищаем сессию
                    if 'post_session' in context.user_data:
                        del context.user_data['post_session']
                    if 'post_results' in context.user_data:
                        del context.user_data['post_results']
                    
                except Exception as e:
                    logger.error(f"Error saving post: {e}")
                    await query.edit_message_text(
                        "❌ *Ошибка при сохранении!*\n"
                        "Проверьте логи или попробуйте позже.",
                        parse_mode=ParseMode.MARKDOWN
                    )
        
        elif data == 'edit_post':
            # Режим редактирования
            await query.edit_message_text(
                "✏️ *Режим редактирования*\n\n"
                "Выберите действие:",
                reply_markup=get_edit_keyboard()
            )
            return States.EDIT_CHOICE
        
        elif data == 'cancel_post':
            await query.edit_message_text(
                "❌ *Обработка поста отменена*",
                reply_markup=get_main_keyboard()
            )
            
            # Очищаем сессию
            if 'post_session' in context.user_data:
                del context.user_data['post_session']
            if 'post_results' in context.user_data:
                del context.user_data['post_results']
            
            return ConversationHandler.END
        
        return ConversationHandler.END
    
    async def calculate_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начать подсчет итогов"""
        await update.message.reply_text(
            "🧮 *Подсчет итогов*\n\n"
            "Введите начальную дату периода (ГГГГ-ММ-ДД):\n"
            "Пример: `2024-01-01`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None
        )
        return States.CALCULATE_START
    
    async def calculate_process_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка начальной даты"""
        start_date = update.message.text.strip()
        
        if not validate_date(start_date):
            await update.message.reply_text(
                "❌ *Некорректная дата!*\n"
                "Используйте формат ГГГГ-ММ-ДД\n"
                "Попробуйте еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return States.CALCULATE_START
        
        context.user_data['calc_start'] = start_date
        
        await update.message.reply_text(
            f"✅ Начальная дата: `{start_date}`\n\n"
            "Введите конечную дату периода (ГГГГ-ММ-ДД):\n"
            f"*Текущая дата:* `{datetime.now().strftime('%Y-%m-%d')}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.CALCULATE_END
    
    async def calculate_process_end(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка конечной даты и подсчет"""
        end_date = update.message.text.strip()
        
        if not validate_date(end_date):
            await update.message.reply_text(
                "❌ *Некорректная дата!*\n"
                "Используйте формат ГГГГ-ММ-ДД\n"
                "Попробуйте еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return States.CALCULATE_END
        
        start_date = context.user_data['calc_start']
        
        # Проверяем, что начальная дата раньше конечной
        if start_date > end_date:
            await update.message.reply_text(
                "❌ *Начальная дата должна быть раньше конечной!*",
                parse_mode=ParseMode.MARKDOWN
            )
            return States.CALCULATE_END
        
        # Показываем индикатор загрузки
        loading_msg = await update.message.reply_text(
            "⏳ *Подсчитываю итоги...*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Рассчитываем итоги
            results = calculator.calculate_period_totals(start_date, end_date)
            
            # Генерируем отчет
            report = format_report(results)
            
            # Отправляем отчет
            await loading_msg.delete()
            
            # Разбиваем на части, если отчет слишком большой
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for part in parts:
                    await update.message.reply_text(
                        part,
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await update.message.reply_text(
                    report,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_calculate_keyboard()
                )
            
            # Сохраняем результаты для возможного экспорта
            context.user_data['last_calculation'] = {
                'period': f"{start_date}_{end_date}",
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error calculating totals: {e}")
            await loading_msg.delete()
            await update.message.reply_text(
                f"❌ *Ошибка при подсчете!*\n\n"
                f"Детали: `{str(e)}`",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END
    
    async def export_excel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспорт в Excel"""
        last_calc = context.user_data.get('last_calculation')
        
        if not last_calc:
            await update.message.reply_text(
                "❌ *Нет данных для экспорта!*\n"
                "Сначала выполните подсчет итогов.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        loading_msg = await update.message.reply_text(
            "⏳ *Генерирую Excel файл...*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Экспортируем данные
            excel_data = self.db.export_to_excel(last_calc['period'])
            
            await loading_msg.delete()
            
            # Отправляем файл
            await update.message.reply_document(
                document=io.BytesIO(excel_data),
                filename=f"matsuni_report_{last_calc['period']}.xlsx",
                caption=f"📊 *Отчет за период {last_calc['period'].replace('_', ' - ')}*",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            await loading_msg.delete()
            await update.message.reply_text(
                f"❌ *Ошибка при экспорте!*\n\n"
                f"Детали: `{str(e)}`",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def add_exclusion_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавить исключение"""
        await update.message.reply_text(
            "⚠️ *Добавление исключения*\n\n"
            "Введите username участника для исключения:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None
        )
        return States.EXCLUSION_ADD
    
    async def process_exclusion_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка username для исключения"""
        username = update.message.text.strip()
        
        # Проверяем существование участника
        members = [m['username'] for m in self.db.get_members()]
        if username not in members:
            await update.message.reply_text(
                f"❌ *Участник @{username} не найден!*\n"
                "Проверьте правильность username.",
                parse_mode=ParseMode.MARKDOWN
            )
            return States.EXCLUSION_ADD
        
        context.user_data['exclusion_user'] = username
        
        await update.message.reply_text(
            f"✅ Участник: @{username}\n\n"
            "Введите название поста для исключения:\n"
            "Пример: `vibro` (или `all` для всех постов)",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.EXCLUSION_POST
    
    async def process_exclusion_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка поста для исключения"""
        post_name = update.message.text.strip()
        context.user_data['exclusion_post'] = post_name
        
        await update.message.reply_text(
            f"✅ Пост: `{post_name}`\n\n"
            "Введите причину исключения (необязательно):\n"
            "Или нажмите /skip",
            parse_mode=ParseMode.MARKDOWN
        )
        return States.EXCLUSION_REASON
    
    async def process_exclusion_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка причины исключения и сохранение"""
        reason = update.message.text.strip() if update.message.text != '/skip' else ''
        
        username = context.user_data['exclusion_user']
        post_name = context.user_data['exclusion_post']
        
        try:
            self.db.add_exclusion(username, post_name, reason)
            
            await update.message.reply_text(
                f"✅ *Исключение добавлено!*\n\n"
                f"• 👤 Участник: @{username}\n"
                f"• 📝 Пост: `{post_name}`\n"
                f"• 📋 Причина: `{reason or 'не указана'}`\n\n"
                f"Теперь @{username} не будет учитываться "
                f"в подсчетах для поста `{post_name}`.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_keyboard()
            )
            
            # Очищаем временные данные
            del context.user_data['exclusion_user']
            del context.user_data['exclusion_post']
            
        except Exception as e:
            logger.error(f"Error adding exclusion: {e}")
            await update.message.reply_text(
                "❌ *Ошибка при добавлении исключения!*",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущего действия"""
        await update.message.reply_text(
            "❌ *Действие отменено*",
            reply_markup=get_main_keyboard()
        )
        
        # Очищаем все временные данные
        keys_to_remove = [
            'new_member', 'post_session', 'post_results',
            'calc_start', 'last_calculation',
            'exclusion_user', 'exclusion_post'
        ]
        
        for key in keys_to_remove:
            if key in context.user_data:
                del context.user_data[key]
        
        return ConversationHandler.END

def main():
    """Запуск бота"""
    # Создаем экземпляр бота
    bot = MatsuniBot()
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Диалог для добавления участника
    add_member_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^➕ Добавить участника$'), bot.add_member_start),
            CommandHandler('add_member', bot.add_member_start)
        ],
        states={
            States.ADD_MEMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.add_member_process)
            ],
            States.ADD_MEMBER_DATE: [
                MessageHandler(filters.TEXT, bot.add_member_date),
                CommandHandler('skip', bot.add_member_date)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)]
    )
    
    # Диалог для нового поста
    new_post_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^📝 Новый пост$'), bot.new_post_start),
            CommandHandler('new_post', bot.new_post_start)
        ],
        states={
            States.POST_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.process_post_name)
            ],
            States.POST_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.process_post_date)
            ],
            States.POST_LIKES: [
                MessageHandler(filters.PHOTO, bot.process_likes_images),
                MessageHandler(filters.Regex('^✅ Завершить этап$'), bot.process_likes_images)
            ],
            States.POST_COMMENTS: [
                MessageHandler(filters.PHOTO, bot.process_comments_images),
                MessageHandler(filters.Regex('^✅ Завершить этап$'), bot.process_comments_images)
            ],
            States.POST_CONFIRM: [
                CallbackQueryHandler(bot.button_callback)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)]
    )
    
    # Диалог для подсчета итогов
    calculate_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^🧮 Подсчитать итог$'), bot.calculate_start),
            CommandHandler('calculate', bot.calculate_start)
        ],
        states={
            States.CALCULATE_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.calculate_process_start)
            ],
            States.CALCULATE_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.calculate_process_end)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)]
    )
    
    # Диалог для добавления исключений
    exclusion_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^⚠️ Добавить исключение$'), bot.add_exclusion_start),
            CommandHandler('exclude', bot.add_exclusion_start)
        ],
        states={
            States.EXCLUSION_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.process_exclusion_username)
            ],
            States.EXCLUSION_POST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.process_exclusion_post)
            ],
            States.EXCLUSION_REASON: [
                MessageHandler(filters.TEXT, bot.process_exclusion_reason),
                CommandHandler('skip', bot.process_exclusion_reason)
            ]
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)]
    )
    
    # Основные обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(add_member_conv)
    application.add_handler(new_post_conv)
    application.add_handler(calculate_conv)
    application.add_handler(exclusion_conv)
    
    # Дополнительные обработчики
    application.add_handler(MessageHandler(
        filters.Regex('^📋 Список участников$'), bot.list_members
    ))
    application.add_handler(MessageHandler(
        filters.Regex('^📤 Экспорт в Excel$'), bot.export_excel
    ))
    
    # Запускаем бота
    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()