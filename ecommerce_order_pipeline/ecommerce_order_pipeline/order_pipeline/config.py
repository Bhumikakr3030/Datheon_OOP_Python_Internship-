"""Thread-safe Singleton configuration manager (process-local)."""
from threading import RLock


class ConfigManager:
    _instance = None
    _instance_lock = RLock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, initial=None):
        with self._instance_lock:
            if self._initialized:
                return
            self.__values = dict(initial or {})
            self.__lock = RLock()
            self._initialized = True

    def get(self, key, default=None):
        with self.__lock:
            return self.__values.get(key, default)

    def set(self, key, value):
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Configuration key cannot be empty.")
        with self.__lock:
            self.__values[key] = value

    def snapshot(self):
        with self.__lock:
            return dict(self.__values)
