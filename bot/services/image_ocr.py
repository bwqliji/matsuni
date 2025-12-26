import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
import re
import cv2
import numpy as np
from typing import List, Tuple, Dict
import logging
from concurrent.futures import ThreadPoolExecutor
import cachetools

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Улучшенный процессор изображений с кэшированием"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.cache = cachetools.TTLCache(maxsize=100, ttl=3600)  # 1 час
        
    def preprocess_image(self, image_bytes: bytes) -> Image.Image:
        """Предобработка изображения для лучшего распознавания"""
        # Конвертируем в OpenCV формат
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Конвертируем в grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Применяем адаптивный threshold
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Убираем шум
        kernel = np.ones((1, 1), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Увеличиваем контраст
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        thresh = clahe.apply(thresh)
        
        # Конвертируем обратно в PIL
        result = Image.fromarray(thresh)
        
        # Улучшаем резкость
        enhancer = ImageEnhance.Sharpness(result)
        result = enhancer.enhance(2.0)
        
        return result
    
    @cachetools.cached(lambda self, image_bytes: cachetools.keys.hashkey(image_bytes), 
                      cache=lambda self: self.cache)
    def extract_text(self, image_bytes: bytes, lang: str = 'eng+rus') -> str:
        """Извлечь текст из изображения с кэшированием"""
        try:
            # Предобработка
            processed_image = self.preprocess_image(image_bytes)
            
            # Конфигурация для соцсетей
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@._-: '
            
            # Извлекаем текст
            text = pytesseract.image_to_string(
                processed_image,
                lang=lang,
                config=custom_config
            )
            
            # Очищаем текст
            text = self._clean_text(text)
            
            logger.debug(f"Extracted text length: {len(text)}")
            return text.lower()
            
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return ""
    
    def _clean_text(self, text: str) -> str:
        """Очистка текста"""
        # Убираем лишние пробелы
        text = ' '.join(text.split())
        
        # Исправляем common OCR ошибки
        corrections = {
            '@5': '@s',
            '1': 'l',
            '0': 'o',
            'vv': 'w',
            'rn': 'm',
        }
        
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        
        return text
    
    def find_usernames(self, text: str, members_list: List[str], 
                      min_confidence: float = 0.8) -> List[Tuple[str, float]]:
        """Найти имена пользователей с уверенностью"""
        found = []
        
        # Создаем паттерны для поиска
        patterns = [
            r'@([a-zA-Z0-9_.]+)',  # @username
            r'([a-zA-Z0-9_.]+)\s*:',  # username:
            r'([a-zA-Z0-9_.]+)\s*любит',  # для Instagram
            r'([a-zA-Z0-9_.]+)\s*нравится',
        ]
        
        all_patterns = '|'.join(patterns)
        matches = re.findall(all_patterns, text, re.IGNORECASE)
        
        # Обрабатываем найденные совпадения
        for match in matches:
            # re.findall возвращает кортежи для групп, выбираем непустые
            username = match if isinstance(match, str) else ''.join(match)
            
            # Проверяем каждого участника
            for member in members_list:
                confidence = self._calculate_similarity(username.lower(), member.lower())
                if confidence >= min_confidence:
                    found.append((member, confidence))
        
        # Убираем дубликаты, оставляя максимальную уверенность
        unique_found = {}
        for username, confidence in found:
            if username not in unique_found or confidence > unique_found[username]:
                unique_found[username] = confidence
        
        # Сортируем по уверенности
        return sorted(unique_found.items(), key=lambda x: x[1], reverse=True)
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Вычислить схожесть строк (расстояние Левенштейна)"""
        if str1 == str2:
            return 1.0
        
        # Простой алгоритм схожести
        longer = str1 if len(str1) > len(str2) else str2
        shorter = str1 if len(str1) <= len(str2) else str2
        
        # Проверка на подстроку
        if shorter in longer:
            return 0.9
        
        # Вычисляем расстояние Левенштейна
        matrix = [[0] * (len(str2) + 1) for _ in range(len(str1) + 1)]
        
        for i in range(len(str1) + 1):
            matrix[i][0] = i
        for j in range(len(str2) + 1):
            matrix[0][j] = j
        
        for i in range(1, len(str1) + 1):
            for j in range(1, len(str2) + 1):
                cost = 0 if str1[i-1] == str2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # удаление
                    matrix[i][j-1] + 1,      # вставка
                    matrix[i-1][j-1] + cost  # замена
                )
        
        distance = matrix[len(str1)][len(str2)]
        max_len = max(len(str1), len(str2))
        
        if max_len == 0:
            return 1.0
        
        return 1.0 - (distance / max_len)
    
    def batch_process_images(self, images: List[bytes], members_list: List[str]) -> Dict[str, List]:
        """Пакетная обработка изображений"""
        results = {
            'likes': set(),
            'comments': set(),
            'errors': []
        }
        
        futures = []
        for image_bytes in images:
            future = self.executor.submit(
                self._process_single_image,
                image_bytes,
                members_list
            )
            futures.append(future)
        
        # Собираем результаты
        for future in futures:
            try:
                result = future.result(timeout=30)
                results['likes'].update(result['likes'])
                results['comments'].update(result['comments'])
            except Exception as e:
                results['errors'].append(str(e))
                logger.error(f"Error in batch processing: {e}")
        
        return results
    
    def _process_single_image(self, image_bytes: bytes, members_list: List[str]) -> Dict:
        """Обработать одно изображение"""
        text = self.extract_text(image_bytes)
        
        # Определяем тип (лайки или комментарии)
        is_comments = any(word in text for word in ['комментарий', 'comment', 'ответил', 'ответила'])
        
        found_usernames = self.find_usernames(text, members_list)
        
        return {
            'likes': [u for u, _ in found_usernames] if not is_comments else [],
            'comments': [u for u, _ in found_usernames] if is_comments else [],
            'text_sample': text[:100] if text else ''
        }

# Глобальный экземпляр процессора
image_processor = ImageProcessor()