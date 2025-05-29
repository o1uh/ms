import logging
import os
from datetime import datetime

LOG_DIR = "logs" # Папка для хранения логов, будет создана в корне проекта

def setup_logger(logger_name, log_file_prefix):
    """Настраивает и возвращает логгер."""

    # Создаем папку для логов, если ее нет
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    # Формируем имя файла лога с датой и временем
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"{log_file_prefix}_{timestamp}.log"
    log_filepath = os.path.join(LOG_DIR, log_filename)

    # Создаем логгер
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG) # Устанавливаем минимальный уровень логирования (DEBUG и выше)

    # Предотвращаем дублирование обработчиков, если функция вызывается несколько раз для одного логгера
    if logger.hasHandlers():
        logger.handlers.clear()

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG) # Уровень для файла

    # Создаем обработчик для вывода в консоль (опционально, но удобно для отладки)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO) # Уровень для консоли (например, INFO и выше)

    # Создаем форматтер и добавляем его к обработчикам
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger