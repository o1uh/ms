import sys
from PySide6.QtWidgets import QApplication


try:
    from client.main_window import ChatClientWindow
except ModuleNotFoundError:
    print(
        "Ошибка: Не удалось импортировать ChatClientWindow. Убедитесь, что структура проекта верна и __init__.py файлы на месте.")
    print(f"Текущий sys.path: {sys.path}")
    sys.exit(1)

if __name__ == '__main__':
    # main_app_logger = setup_logger('ClientAppRoot', 'client_app_root_session')
    # main_app_logger.info("Запуск клиентского приложения из run_client.py...")

    app = QApplication(sys.argv)
    main_window = ChatClientWindow()
    main_window.show()
    sys.exit(app.exec())