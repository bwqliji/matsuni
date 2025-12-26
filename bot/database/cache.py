# bot/database/cache.py
import cachetools

class SimpleCacheManager:
    """Простой менеджер кэша"""
    def __init__(self):
        self._caches = {}
    
    def get_cache(self, name: str, ttl: int = 300, maxsize: int = 1000):
        """Получить кэш"""
        if name not in self._caches:
            self._caches[name] = cachetools.TTLCache(maxsize=maxsize, ttl=ttl)
        return self._caches[name]
    
    def clear_cache(self, name: str):
        """Очистить кэш"""
        if name in self._caches:
            self._caches[name].clear()

# Глобальный экземпляр
cache_manager = SimpleCacheManager()