#!/bin/bash
# Скрипт сборки для Render

echo "🚀 Начинаем сборку для Python 3.13..."

# Обновляем pip и setuptools
python -m pip install --upgrade pip setuptools wheel

# Устанавливаем зависимости
pip install -r requirements.txt

echo "✅ Сборка завершена!"