# ms/run_client.py
import sys
from PySide6.QtWidgets import QApplication

# Настройка sys.path, если client не установлен как пакет и run_client.py в корне
import os

# Если run_client.py в корне (ms/), а client - подпапка, то client уже должен быть виден.
# Если есть проблемы с импортом client.main_window, попробуйте:
# SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # ms/
# sys.path.insert(0, SCRIPT_DIR) # Добавляем корень проекта в начало пути

try:
    from client.main_window import ChatClientWindow
    # from logger import setup_logger # logger используется внутри main_window
except ModuleNotFoundError:
    print(
        "Ошибка: Не удалось импортировать ChatClientWindow. Убедитесь, что структура проекта верна и __init__.py файлы на месте.")
    print(f"Текущий sys.path: {sys.path}")
    sys.exit(1)

if __name__ == '__main__':
    # Логгер инициализируется внутри ChatClientWindow (и SocketHandler)
    # main_app_logger = setup_logger('ClientAppRoot', 'client_app_root_session')
    # main_app_logger.info("Запуск клиентского приложения из run_client.py...")

    app = QApplication(sys.argv)
    main_window = ChatClientWindow()
    main_window.show()
    sys.exit(app.exec())