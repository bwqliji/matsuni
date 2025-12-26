import os
from flask import Flask, jsonify
from telegram.ext import Application

app = Flask(__name__)

# Инициализация бота
bot_app = None

def init_bot():
    """Инициализация Telegram бота"""
    global bot_app
    from config.settings import BOT_TOKEN
    from bot.main import main
    
    if not bot_app:
        bot_app = Application.builder().token(BOT_TOKEN).build()
    
    return bot_app

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "OK", 
        "message": "Matsuni Bot is running",
        "endpoints": [
            "/health",
            "/webhook",
            "/api/status"
        ]
    })

@app.route('/health')
def health_check():
    """Health check для Render"""
    return jsonify({"status": "healthy"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook для Telegram"""
    # Эта функция будет обрабатывать webhook от Telegram
    # Пока возвращаем заглушку
    return jsonify({"status": "webhook_received"}), 200

@app.route('/api/status')
def api_status():
    """API статуса бота"""
    try:
        bot_status = "initialized" if bot_app else "not_initialized"
        return jsonify({
            "bot_status": bot_status,
            "server_time": os.environ.get("TZ", "UTC"),
            "environment": os.environ.get("ENVIRONMENT", "production")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_bot():
    """Запуск Telegram бота в отдельном потоке"""
    try:
        from bot.main import main
        print("Starting Telegram bot...")
        main()
    except Exception as e:
        print(f"Error starting bot: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    
    # Запускаем бот в отдельном потоке
    import threading
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=port)